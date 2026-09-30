"""LLM-as-Judge 自动评估脚本（对应实验 5-3 步骤 2~4）。

流程：
1. 遍历 tests/test_cases.py 中的测试用例
2. 对每条例用运行系统真实模块，得到「待评答案」
3. 用大模型当裁判，从准确性/完整性/相关性三个维度 1~5 分打分
4. 每条用例重复采样多次（默认 3 次）取均值并计算标准差，降低单次随机波动的影响
5. 汇总评分表并保存为 CSV（可按轮次打标签，便于「基线 vs 改进后」一键对比）

运行方式：
    python tests/evaluate.py                    # 默认每条采样 3 次
    python tests/evaluate.py --repeat 1         # 快速跑一遍（结果波动大，仅供冒烟验证）
    python tests/evaluate.py --tag baseline     # 输出 evaluation_result_baseline.csv
"""
import argparse
import csv
import os
import statistics
import sys

# 允许从项目根目录导入模块（llm / prompts / games），以及同目录的 test_cases
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm import chat_json, usage_of  # noqa: E402
from prompts import LLM_JUDGE_PROMPT  # noqa: E402
from games import MAX_ACTION_CHARS, clamp_text, adventure, quiz  # noqa: E402
from test_cases import TEST_CASES  # noqa: E402

FIELD_NAMES = ["id", "category", "name", "type", "accuracy",
               "completeness", "relevance", "avg", "std", "runs", "reason"]


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
    """运行一条大模型用例，返回 (待评答案文本, usage)。"""
    typ = case["type"]
    args = case["args"]

    if typ == "judge":
        result, usage = quiz.judge(
            args["question_text"], args["answer"], args["reply"]
        )
        output = f"correct={result['correct']}, comment={result['comment']}"
        return output, usage

    if typ == "adventure":
        history = adventure.new_history()
        state, usage = adventure.adventure_turn(history, args["action"])
        output = (
            f"story={state['story']}\n"
            f"options={state['options']}\n"
            f"game_over={state['game_over']}"
        )
        return output, usage

    if typ == "quiz":
        data, usage = quiz.ai_quiz(args["topic"], args["difficulty"])
        output = f"question={data['question']}\nanswer={data['answer']}\nhint={data['hint']}"
        return output, usage

    raise ValueError(f"未知测试类型：{typ}")


def run_program_check(case: dict):
    """程序级断言：不调用大模型，直接验证代码防护逻辑是否生效。

    返回 (断言描述, 是否通过)。这类用例不消耗 token，可离线复现，
    专门用来守住「边界与安全」的回归。
    """
    args = case["args"]
    check = args.get("check", "empty_input")

    if check == "empty_input":
        # 空输入应在触达 API 之前被 games 层拦截
        try:
            adventure.adventure_turn(adventure.new_history(), args.get("action", ""))
        except ValueError as exc:
            return f"空输入被拦截并抛出 ValueError（{exc}），未触发任何 API 调用。", True
        return "空输入未被拦截，存在空转调用风险。", False

    if check == "answer_leaked":
        leaked_flag = quiz.answer_leaked(args["leaked"])
        clean_flag = quiz.answer_leaked(args["clean"])
        desc = (f"泄露样例检测={leaked_flag}（应为 True）；"
                f"正常样例检测={clean_flag}（应为 False）")
        return desc, (leaked_flag is True and clean_flag is False)

    if check == "clamp_text":
        limit = args.get("max_chars", MAX_ACTION_CHARS)
        long_text, cut = clamp_text("测" * (limit + 100), limit)
        short_text, cut2 = clamp_text("走进森林", limit)
        desc = (f"超长输入截断={cut}、截断后长度={len(long_text)}/{limit}；"
                f"正常输入截断={cut2}、内容={short_text!r}")
        return desc, (cut and len(long_text) == limit
                      and not cut2 and short_text == "走进森林")

    raise ValueError(f"未知的程序级检查项：{check}")


def _merge_tokens(acc: dict, usage: dict | None):
    """累加一次调用的 token 用量。"""
    if not usage:
        return
    acc["prompt"] += usage["prompt_tokens"]
    acc["completion"] += usage["completion_tokens"]
    acc["total"] += usage["total_tokens"]


def _mean(values):
    return round(statistics.mean(values), 2) if values else "-"


def main():
    parser = argparse.ArgumentParser(description="AI 游戏乐园 —— 测试用例评估")
    parser.add_argument("--repeat", type=int, default=3,
                        help="每条用例的采样次数（取均值与标准差，默认 3）")
    parser.add_argument("--tag", default="",
                        help="本轮评估标签，输出 evaluation_result_<tag>.csv 便于对比")
    args = parser.parse_args()
    repeat = max(1, args.repeat)

    total_tokens = {"prompt": 0, "completion": 0, "total": 0}
    rows = []

    print("=" * 100)
    print("AI 游戏乐园 —— 测试用例评估报告（LLM-as-Judge）")
    print(f"用例总数：{len(TEST_CASES)}　每条采样次数：{repeat}"
          + (f"　轮次标签：{args.tag}" if args.tag else ""))
    print("=" * 100)

    for case in TEST_CASES:
        cid, cname, category = case["id"], case["name"], case["category"]
        print(f"\n[{cid}] {cname}（{category}）")

        # ---------------- 程序级用例：直接断言，不消耗 token ----------------
        if case["type"] == "program":
            try:
                desc, passed = run_program_check(case)
            except Exception as exc:  # noqa: BLE001 - 断言本身出错也算未通过
                desc, passed = f"检查执行失败：{exc}", False
            print(f"  {'✓ 通过' if passed else '✗ 未通过'}：{desc}")
            rows.append({"id": cid, "category": category, "name": cname,
                         "type": "program",
                         "accuracy": "PASS" if passed else "FAIL",
                         "completeness": "-", "relevance": "-",
                         "avg": "-", "std": "-", "runs": repeat,
                         "reason": desc})
            continue

        # ---------------- 大模型用例：重复采样 + 裁判打分 ----------------
        run_scores, run_dims, failures = [], [], 0
        last_reason = ""
        for i in range(repeat):
            try:
                output, usage = run_case(case)
            except Exception as exc:
                failures += 1
                print(f"  第 {i + 1}/{repeat} 次：✗ 运行失败（{exc}）")
                continue
            _merge_tokens(total_tokens, usage)

            try:
                score, j_usage = llm_judge(case["question"], case["reference"], output)
            except Exception as exc:
                failures += 1
                print(f"  第 {i + 1}/{repeat} 次：✗ 裁判评分失败（{exc}）")
                continue
            _merge_tokens(total_tokens, j_usage)

            acc = score.get("accuracy")
            comp = score.get("completeness")
            rel = score.get("relevance")
            nums = [v for v in (acc, comp, rel) if isinstance(v, (int, float))]
            avg = round(sum(nums) / len(nums), 2) if nums else None
            last_reason = score.get("reason", "") or last_reason
            if avg is None:
                print(f"  第 {i + 1}/{repeat} 次：✗ 裁判未返回有效分数")
                continue
            run_scores.append(avg)
            run_dims.append((acc, comp, rel))
            print(f"  第 {i + 1}/{repeat} 次：准确性={acc} 完整性={comp} "
                  f"相关性={rel} 平均={avg}")

        if not run_scores:
            print("  → 该用例本轮无有效评分，已标记为失败")
            rows.append({"id": cid, "category": category, "name": cname,
                         "type": case["type"], "accuracy": "-", "completeness": "-",
                         "relevance": "-", "avg": "-", "std": "-", "runs": 0,
                         "reason": f"全部采样失败（{failures} 次）"})
            continue

        avg = round(statistics.mean(run_scores), 2)
        std = round(statistics.pstdev(run_scores), 2) if len(run_scores) > 1 else 0.0
        dim_avg = {
            key: _mean([d[i] for d in run_dims if isinstance(d[i], (int, float))])
            for i, key in enumerate(("accuracy", "completeness", "relevance"))
        }
        tail = f"　（其中 {failures} 次失败）" if failures else ""
        print(f"  → {len(run_scores)} 次采样：平均={avg}　标准差={std}{tail}")

        rows.append({"id": cid, "category": category, "name": cname,
                     "type": case["type"],
                     "accuracy": dim_avg["accuracy"],
                     "completeness": dim_avg["completeness"],
                     "relevance": dim_avg["relevance"],
                     "avg": avg, "std": std, "runs": len(run_scores),
                     "reason": last_reason})

    # ------------------------------------------------------------------
    # 汇总
    # ------------------------------------------------------------------
    print("\n" + "=" * 100)
    print("汇总")
    print("=" * 100)

    scored = [r for r in rows if isinstance(r["avg"], (int, float))]
    if scored:
        print(f"参与 LLM 评分的用例数：{len(scored)}/{len(rows)}")
        print(f"三维度平均分：{round(statistics.mean([r['avg'] for r in scored]), 2)}")
        for dim in ("accuracy", "completeness", "relevance"):
            vals = [r[dim] for r in rows if isinstance(r[dim], (int, float))]
            if vals:
                print(f"  {dim} 平均：{round(statistics.mean(vals), 2)}")
        stds = [r["std"] for r in scored if isinstance(r["std"], (int, float))]
        if stds:
            print(f"  各用例跨轮标准差均值：{round(statistics.mean(stds), 3)}"
                  f"（越小说明输出越稳定）")

    program_rows = [r for r in rows if r["type"] == "program"]
    if program_rows:
        passed = sum(1 for r in program_rows if r["accuracy"] == "PASS")
        print(f"程序级防护用例：{passed}/{len(program_rows)} 通过")

    print(f"累计 Token 消耗：输入 {total_tokens['prompt']:,} / 输出 "
          f"{total_tokens['completion']:,} / 总计 {total_tokens['total']:,}")

    # ------------------------------------------------------------------
    # 保存 CSV（带轮次标签，便于基线/改进对比）
    # ------------------------------------------------------------------
    fname = f"evaluation_result_{args.tag}.csv" if args.tag else "evaluation_result.csv"
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), fname)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELD_NAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n评分表已保存至：{out_path}")


if __name__ == "__main__":
    main()
