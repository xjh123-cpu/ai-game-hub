/* AI 游戏乐园 —— 前端逻辑（通过 window.pywebview.api 调用后端） */

const $ = (sel) => document.querySelector(sel);

/* ---------- 视图切换 ---------- */
function showView(id) {
  document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
  $('#' + id).classList.remove('hidden');
}

/* ---------- 加载遮罩 ---------- */
function showLoading(on) {
  $('#loading').classList.toggle('hidden', !on);
}

/* ---------- API 调用封装 ---------- */
async function api(method, ...args) {
  if (window.pywebview && window.pywebview.api) {
    return await window.pywebview.api[method](...args);
  }
  return { ok: false, error: '桌面桥接不可用，请通过 main.py 启动' };
}

/* ---------- 游戏状态 ---------- */
let quizScore = 0;
let quizCombo = 0;
let quizHigh = 0;
let currentHintCost = 1;

/* ============================================================
 * 初始化
 * ============================================================ */
document.addEventListener('DOMContentLoaded', async () => {
  // 大厅卡片点击
  document.querySelectorAll('.card').forEach(card => {
    card.addEventListener('click', () => {
      const game = card.dataset.game;
      if (game === 'adventure') enterAdventure();
      else enterQuiz();
    });
  });

  // 返回按钮
  document.querySelectorAll('[data-back]').forEach(btn => {
    btn.addEventListener('click', () => showView('view-home'));
  });

  // Key 设置
  $('#btn-settings').addEventListener('click', openKeyModal);
  $('#key-cancel').addEventListener('click', closeKeyModal);
  $('#key-save').addEventListener('click', saveKey);

  // 文字冒险
  $('#btn-adv-act').addEventListener('click', doAdventureAction);
  $('#adv-input').addEventListener('keydown', e => { if (e.key === 'Enter') doAdventureAction(); });
  $('#btn-adv-restart').addEventListener('click', startAdventure);
  $('#btn-adv-save').addEventListener('click', () => saveAdventure(1));
  $('#btn-adv-load').addEventListener('click', () => loadAdventure(1));

  // 猜谜
  $('#btn-quiz-new').addEventListener('click', newQuiz);
  $('#btn-quiz-submit').addEventListener('click', submitQuiz);
  $('#quiz-input').addEventListener('keydown', e => { if (e.key === 'Enter') submitQuiz(); });
  $('#btn-quiz-hint').addEventListener('click', useHint);

  // 刷新大厅统计
  refreshHomeStats();

  // 首次启动：未配置 Key 则弹窗提示
  const keyRes = await api('has_key');
  if (keyRes.ok && !keyRes.has_key) openKeyModal();
});

/* ============================================================
 * 大厅统计
 * ============================================================ */
async function refreshHomeStats() {
  const adv = await api('adv_max_turns');
  const quiz = await api('quiz_high_score');
  if (adv.ok) $('#adv-high').textContent = adv.max_turns;
  if (quiz.ok) {
    quizHigh = quiz.high_score;
    $('#quiz-high').textContent = quiz.high_score;
    $('#quiz-high2').textContent = quiz.high_score;
  }
}

/* ============================================================
 * API Key 弹窗
 * ============================================================ */
function openKeyModal() {
  $('#key-modal').classList.remove('hidden');
  $('#key-msg').textContent = '';
  $('#key-input').value = '';
}
function closeKeyModal() {
  $('#key-modal').classList.add('hidden');
}
async function saveKey() {
  const key = $('#key-input').value.trim();
  if (!key) { $('#key-msg').textContent = '请输入密钥'; $('#key-msg').className = 'msg bad'; return; }
  const res = await api('set_key', key);
  const msg = $('#key-msg');
  if (res.ok) {
    msg.textContent = '✅ 保存成功';
    msg.className = 'msg ok';
    setTimeout(closeKeyModal, 700);
  } else {
    msg.textContent = '❌ ' + (res.error || '保存失败');
    msg.className = 'msg bad';
  }
}

/* ============================================================
 * 文字冒险
 * ============================================================ */
async function enterAdventure() {
  showView('view-adventure');
  $('#adv-turns').textContent = '0';
  $('#adv-story').innerHTML = '<p class="placeholder">点击「开始冒险」进入迷雾林，剧情将实时生成……</p>';
  $('#adv-options').innerHTML = '';
  $('#adv-over-row').classList.add('hidden');
  $('#adv-input-row').classList.remove('hidden');
  await api('adv_new');
}

async function startAdventure() {
  showLoading(true);
  const res = await api('adv_start');
  showLoading(false);
  if (!res.ok) { alert(res.error || '开局失败'); return; }
  renderAdventure(res);
}

async function doAdventureAction() {
  const input = $('#adv-input');
  const action = input.value.trim();
  if (!action) return;
  input.value = '';
  await runAdventureTurn(action);
}

async function runAdventureTurn(action) {
  showLoading(true);
  const res = await api('adv_turn', action);
  showLoading(false);
  if (!res.ok) { alert(res.error || '行动失败'); return; }
  renderAdventure(res);
}

function renderAdventure(res) {
  $('#adv-turns').textContent = res.turns;
  $('#adv-story').textContent = res.story;
  const optBox = $('#adv-options');
  optBox.innerHTML = '';
  if (!res.game_over) {
    res.options.forEach((opt, i) => {
      const b = document.createElement('button');
      b.textContent = `${i + 1}. ${opt}`;
      b.addEventListener('click', () => runAdventureTurn(opt));
      optBox.appendChild(b);
    });
    $('#adv-input-row').classList.remove('hidden');
    $('#adv-over-row').classList.add('hidden');
  } else {
    $('#adv-input-row').classList.add('hidden');
    $('#adv-over-row').classList.remove('hidden');
  }
}

async function saveAdventure(slot) {
  const res = await api('adv_save', slot);
  alert(res.ok ? '💾 已存档' : '❌ ' + (res.error || '存档失败'));
}

async function loadAdventure(slot) {
  showLoading(true);
  const res = await api('adv_load', slot);
  showLoading(false);
  if (!res.ok) { alert('❌ ' + (res.error || '读档失败')); return; }
  renderAdventure(res);
  alert('📂 读档成功');
}

/* ============================================================
 * 猜谜闯关
 * ============================================================ */
async function enterQuiz() {
  showView('view-quiz');
  $('#quiz-question').innerHTML = '<p class="placeholder">选择主题与难度，点击「出题」开始挑战</p>';
  $('#quiz-hint').classList.add('hidden');
  $('#quiz-result').innerHTML = '';
  quizScore = 0;
  quizCombo = 0;
  updateQuizBar();
}

function updateQuizBar() {
  $('#quiz-score').textContent = quizScore;
  $('#quiz-combo').textContent = quizCombo;
  $('#quiz-high2').textContent = quizHigh;
  $('#quiz-combo-pill').style.display = quizCombo >= 2 ? '' : 'none';
}

async function newQuiz() {
  const topic = $('#quiz-topic').value.trim() || '动物';
  const difficulty = $('#quiz-difficulty').value;
  showLoading(true);
  const res = await api('quiz_new', topic, difficulty);
  showLoading(false);
  if (!res.ok) { alert(res.error || '出题失败'); return; }
  $('#quiz-question').textContent = '🎯 ' + res.question;
  $('#quiz-hint').classList.add('hidden');
  $('#quiz-result').innerHTML = '';
  $('#quiz-input').value = '';
  $('#quiz-input').focus();
}

async function useHint() {
  if (quizScore < 1) { alert('积分不足，答对题目可获积分'); return; }
  const res = await api('quiz_hint');
  if (!res.ok) { alert(res.error || '无法获取提示'); return; }
  quizScore -= currentHintCost;
  updateQuizBar();
  $('#quiz-hint').textContent = '💡 ' + res.hint;
  $('#quiz-hint').classList.remove('hidden');
}

async function submitQuiz() {
  const reply = $('#quiz-input').value.trim();
  if (!reply) return;
  showLoading(true);
  const res = await api('quiz_judge', reply);
  showLoading(false);
  if (!res.ok) { alert(res.error || '判定失败'); return; }

  const box = $('#quiz-result');
  if (res.correct) {
    quizCombo += 1;
    const gain = 5 + (quizCombo - 1) * 3;
    quizScore += gain;
    box.innerHTML = `<span class="ok">✅ 回答正确！+${gain} 分</span>（连击 x${quizCombo}）<br><span class="muted">${res.comment || ''}</span>`;
  } else {
    quizCombo = 0;
    box.innerHTML = `<span class="bad">❌ 回答错误</span><br><span class="muted">${res.comment || ''}</span><br>正确答案：${res.answer}`;
  }
  updateQuizBar();

  // 提交最高分
  const hs = await api('quiz_submit_score', quizScore);
  if (hs.ok) quizHigh = hs.high_score;
  updateQuizBar();
}
