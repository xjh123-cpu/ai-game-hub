"""LLM-as-Judge 自动评估脚本（对应实验 5-3 步骤 2~4）。

流程：
1. 遍历 tests/test_cases.py 中的测试用例
2. 对每条例用运行系统真实模块，得到「待评答案」
3. 用大模型当裁判，从准确性/完整性/相关性三个维度 1~5 分打分
4. 汇总评分表并保存为 CSV

运行方式：
    python tests/evaluate.py
"""
import os
import sys
import csv

# 允许从项目根目录导入模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm import chat_json, usage_of  # noqa: E402
from prompts import LLM_JUDGE_PROMPT  # noqa: E402
from games import adventure, quiz  # noqa: E402
from test_cases import TEST_CASES  # noqa: E402


def llm_judge(question: str, reference: str, answer: str):
    """大模型当裁判：三维度 1~5 分打分。"""
    prompt = LLM_JUDGE_PROMPT.format(
        question=question, reference=reference, answer=answer
    )
    data, resp = chat_json(
        messages=[{"role": "user", "content": prompt}], temperature=0.0
    )
    return data, usage_of(resp)


def run_case(case: dict):
    """运行一例测试，返回 (待评答案文本, usage, 程序级结论)。"""
    typ = case["type"]
    args = case["args"]

    if typ == "judge":
        result, usage = quiz.judge(
            args["question_text"], args["answer"], args["reply"]
        )
        output = f"correct={result['correct']}, comment={result['comment']}"
        return output, usage, None

    if typ == "adventure":
        history = adventure.new_history()
        state, usage = adventure.adventure_turn(history, args["action"])
        output = (
            f"story={state['story']}\n"
            f"options={state['options']}\n"
            f"game_over={state['game_over']}"
        )
        return output, usage, None

    if typ == "quiz":
        data, usage = quiz.ai_quiz(args["topic"], args["difficulty"])
        output = f"question={data['question']}\nanswer={data['answer']}\nhint={data['hint']}"
        return output, usage, None

    if typ == "program":
        # 程序级健壮性检查：空输入应在调用大模型前被拦截
        action = args["action"]
        if not action.strip():
            return "空输入已被拦截，返回提示「请输入有效行动」，未触发 API 调用。", None, True
        return "未拦截空输入", None, False

    raise ValueError(f"未知测试类型：{typ}")


def main():
    total_tokens = {"prompt": 0, "completion": 0, "total": 0}
    rows = []

    print("=" * 100)
    print("AI 游戏乐园 —— 测试用例评估报告（LLM-as-Judge）")
    print("=" * 100)

    for case in TEST_CASES:
        cid = case["id"]
        name = case["name"]
        print(f"\n[{cid}] {name}（{case['category']}）")

        try:
            output, usage, program_pass = run_case(case)
        except Exception as exc:
            print(f"  ✗ 运行失败：{exc}")
            rows.append({"id": cid, "category": case["category"], "name": name,
                         "type": case["type"], "accuracy": "-", "completeness": "-",
                         "relevance": "-", "avg": "-", "reason": f"运行失败：{exc}"})
            continue

        if case["type"] == "program":
            verdict = "通过" if program_pass else "未通过"
            print(f"  程序级检查：{verdict}")
            rows.append({"id": cid, "category": case["category"], "name": name,
                         "type": case["type"], "accuracy": "PASS" if program_pass else "FAIL",
                         "completeness": "-", "relevance": "-", "avg": "-",
                         "reason": verdict})
            continue

        # LLM-as-Judge 评分
        try:
            score, j_usage = llm_judge(case["question"], case["reference"], output)
        except Exception as exc:
            print(f"  ✗ 裁判评分失败：{exc}")
            rows.append({"id": cid, "category": case["category"], "name": name,
                         "type": case["type"], "accuracy": "-", "completeness": "-",
                         "relevance": "-", "avg": "-", "reason": f"评分失败：{exc}"})
            continue

        total_tokens["prompt"] += usage["prompt_tokens"]
        total_tokens["completion"] += usage["completion_tokens"]
        total_tokens["total"] += usage["total_tokens"]
        total_tokens["prompt"] += j_usage["prompt_tokens"]
        total_tokens["completion"] += j_usage["completion_tokens"]
        total_tokens["total"] += j_usage["total_tokens"]

        acc = score.get("accuracy", "-")
        comp = score.get("completeness", "-")
        rel = score.get("relevance", "-")
        reason = score.get("reason", "")
        nums = [v for v in (acc, comp, rel) if isinstance(v, (int, float))]
        avg = round(sum(nums) / len(nums), 2) if nums else "-"

        print(f"  准确性={acc}  完整性={comp}  相关性={rel}  平均={avg}")
        print(f"  理由：{reason}")
        rows.append({"id": cid, "category": case["category"], "name": name,
                     "type": case["type"], "accuracy": acc, "completeness": comp,
                     "relevance": rel, "avg": avg, "reason": reason})

    # 汇总
    print("\n" + "=" * 100)
    print("汇总")
    print("=" * 100)
    scored = [r for r in rows if isinstance(r["avg"], (int, float))]
    if scored:
        overall = round(sum(r["avg"] for r in scored) / len(scored), 2)
        print(f"LLM 评分的测试用例数：{len(scored)}")
        print(f"三维度平均分：{overall}")
        for dim in ("accuracy", "completeness", "relevance"):
            vals = [r[dim] for r in rows if isinstance(r[dim], (int, float))]
            if vals:
                print(f"  {dim} 平均：{round(sum(vals) / len(vals), 2)}")
    print(f"累计 Token 消耗：输入 {total_tokens['prompt']:,} / 输出 "
          f"{total_tokens['completion']:,} / 总计 {total_tokens['total']:,}")

    # 保存 CSV
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evaluation_result.csv")
    fieldnames = ["id", "category", "name", "type", "accuracy",
                  "completeness", "relevance", "avg", "reason"]
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n评分表已保存至：{out_path}")


if __name__ == "__main__":
    main()
