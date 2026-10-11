/* API 封装：axios 实例 + SSE 流式 + 公共工具 */
/* global axios, marked, ElementPlus */

const API_BASE = window.API_BASE || 'http://127.0.0.1:8000';

const api = axios.create({ baseURL: API_BASE + '/api', timeout: 300000 });

api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem('ro_token');
  if (token) cfg.headers.Authorization = 'Bearer ' + token;
  return cfg;
});

api.interceptors.response.use(
  (resp) => resp.data,
  (err) => {
    let detail = err.message || '网络请求失败';
    if (err.response && err.response.data) {
      const d = err.response.data.detail !== undefined ? err.response.data.detail : err.response.data;
      detail = typeof d === 'string' ? d : JSON.stringify(d);
    }
    if (err.response && err.response.status === 401) {
      localStorage.removeItem('ro_token');
      localStorage.removeItem('ro_user');
      if (!location.hash.startsWith('#/login')) {
        ElementPlus.ElMessage.error('登录已失效，请重新登录');
        location.hash = '#/login';
      }
    }
    return Promise.reject(new Error(detail));
  }
);

/** 读取本地登录信息 */
function getStoredUser() {
  try { return JSON.parse(localStorage.getItem('ro_user') || 'null'); } catch (e) { return null; }
}
function setStoredLogin(token, user) {
  localStorage.setItem('ro_token', token);
  localStorage.setItem('ro_user', JSON.stringify(user));
}
function clearStoredLogin() {
  localStorage.removeItem('ro_token');
  localStorage.removeItem('ro_user');
}

/** SSE 流式请求：onDelta(增量文本) / onDone(结束事件) / onError(错误) */
async function streamSSE(path, body, handlers) {
  const token = localStorage.getItem('ro_token');
  const resp = await fetch(API_BASE + path, {
    method: 'POST',
    headers: Object.assign({ 'Content-Type': 'application/json' }, token ? { Authorization: 'Bearer ' + token } : {}),
    body: JSON.stringify(body || {}),
  });
  if (!resp.ok || !resp.body) {
    let detail = '请求失败(' + resp.status + ')';
    try { const j = await resp.json(); detail = j.detail || detail; } catch (e) { /* ignore */ }
    throw new Error(detail);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buf = '';
  while (true) {
    const r = await reader.read();
    if (r.done) break;
    buf += decoder.decode(r.value, { stream: true });
    const parts = buf.split('\n\n');
    buf = parts.pop();
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith('data:')) continue;
      let evt;
      try { evt = JSON.parse(line.slice(5).trim()); } catch (e) { continue; }
      if (evt.error) { if (handlers.onError) handlers.onError(evt.error); return; }
      if (evt.refs && handlers.onRefs) handlers.onRefs(evt.refs);
      if (evt.delta && handlers.onDelta) handlers.onDelta(evt.delta);
      if (evt.done && handlers.onDone) handlers.onDone(evt);
    }
  }
}

/** 带鉴权的文件下载 */
async function authDownload(path, filename) {
  const token = localStorage.getItem('ro_token');
  const resp = await fetch(API_BASE + path, { headers: token ? { Authorization: 'Bearer ' + token } : {} });
  if (!resp.ok) throw new Error('下载失败(' + resp.status + ')');
  const blob = await resp.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
}

/** Markdown 渲染 */
function renderMd(text) {
  try { return marked.parse(text || '', { breaks: true, gfm: true }); }
  catch (e) { return '<pre>' + (text || '') + '</pre>'; }
}

const TYPE_MAP = { score: '简历评分', analysis: '问题分析', suggestion: '简历优化', rewrite: '简历改写', interview: '面试问题', chat: '对话助手' };
const TYPE_COLORS = { score: '', analysis: 'warning', suggestion: 'success', rewrite: 'danger', interview: 'info', chat: 'success' };
const SCENE_MAP = { score: '简历评分', analysis: '问题分析', suggestion: '简历优化', rewrite: '简历改写', interview: '面试问题', chat: '对话助手' };
const LEVEL_COLORS = { 优秀: '#67c23a', 良好: '#409eff', 合格: '#e6a23c', 待改进: '#f56c6c' };

function fmtTime(s) {
  if (!s) return '-';
  return String(s).replace('T', ' ').slice(0, 19);
}
function fmtDuration(ms) {
  if (ms === null || ms === undefined) return '-';
  return ms >= 1000 ? (ms / 1000).toFixed(1) + 's' : ms + 'ms';
}
