/* 简历优化工作台 v2：顶部选择/上传解析 + 左侧简历文本 + 右侧五大 AI 能力（可选模型与Prompt模板） */
/* global Vue, api, streamSSE, authDownload, fmtTime, LEVEL_COLORS, ElementPlus */

const SCENES = ['score', 'analysis', 'suggestion', 'rewrite', 'interview'];

const Workbench = {
  template: `
  <div class="wb2">
    <!-- 顶部：提示 + 简历选择 / 上传解析 -->
    <div class="wb2-top">
      <div class="tip-row">
        <el-alert type="info" :closable="false" show-icon
          title="上传简历后，系统会解析文本，并将其作为后续 AI 诊断、优化和改写的当前版本"/>
        <el-tag v-if="current" closable @close="clearCurrent" effect="dark" style="flex-shrink:0">
          当前简历：{{ current.title }}
        </el-tag>
      </div>
      <div class="form-row">
        <el-input v-model="form.title" placeholder="简历标题，如：张三-后端开发简历" maxlength="50" style="width:220px" clearable/>
        <el-input v-model="form.target_position" placeholder="目标岗位，如：Python后端开发工程师" maxlength="50" style="width:220px" clearable/>
        <el-select v-model="selectedId" placeholder="已有简历：选择后加载" style="width:240px" filterable clearable @change="onSelectChange">
          <el-option v-for="r in resumeOptions" :key="r.id" :label="r.title" :value="r.id"/>
        </el-select>
        <el-upload :auto-upload="false" :show-file-list="false" :on-change="onPickFile"
          accept=".pdf,.docx,.txt,.html,.htm" style="display:inline-block">
          <el-button type="primary" :loading="parsing"><el-icon><Upload/></el-icon>上传并解析</el-button>
        </el-upload>
        <el-button type="danger" plain :disabled="!current" @click="removeResume"><el-icon><Delete/></el-icon>删除</el-button>
        <el-button plain :disabled="!current" @click="openJd"><el-icon><Document/></el-icon>岗位JD</el-button>
      </div>
    </div>

    <div class="wb2-body">
      <!-- 左：简历文本 -->
      <div class="wb2-left">
        <div class="card-head">
          <b>简历文本</b>
          <span style="flex:1"></span>
          <el-button size="small" type="primary" :loading="saving" @click="saveCurrent"><el-icon><Check/></el-icon>保存当前文本</el-button>
          <el-button size="small" type="success" plain :disabled="!current" @click="downloadWord"><el-icon><Download/></el-icon>下载当前简历</el-button>
        </div>
        <div class="file-info">
          文件：{{ current && current.file_name ? current.file_name : '未上传（可直接粘贴或在线编辑后保存）' }}
        </div>
        <el-collapse class="origin-collapse" v-if="current && current.original_text">
          <el-collapse-item name="origin">
            <template #title><el-icon style="margin-right:6px"><Document/></el-icon>原始解析文本（上传时解析，只读）</template>
            <pre class="origin-text">{{ current.original_text }}</pre>
          </el-collapse-item>
        </el-collapse>
        <el-input v-model="editText" type="textarea" :autosize="{ minRows: 14, maxRows: 24 }"
          class="edit-area" placeholder="在此粘贴或编辑简历文本，AI 诊断、优化和改写均基于此处文本"/>
      </div>

      <!-- 右：AI 能力 -->
      <div class="wb2-right">
        <el-tabs v-model="activeTab" class="wb-tabs">
          <!-- 诊断评分 -->
          <el-tab-pane label="诊断评分" name="score" lazy>
            <div class="ai-toolbar">
              <span class="lbl">模型配置</span>
              <el-select v-model="configId" placeholder="默认（最新启用配置）" style="width:230px" clearable>
                <el-option v-for="c in options.configs" :key="c.id" :label="c.provider + ' · ' + c.model_name" :value="c.id"/>
              </el-select>
              <span class="lbl">Prompt模板</span>
              <el-select v-model="promptSel.score" placeholder="默认模板" style="width:250px" clearable>
                <el-option v-for="p in promptsOf('score')" :key="p.id" :label="p.name + '（' + p.code + '）'" :value="p.id"/>
              </el-select>
              <el-button type="primary" :loading="scoring" @click="startScore"><el-icon><Odometer/></el-icon>生成评分</el-button>
              <span class="hint">结构化输出：0-100 分 + 等级 + 诊断分析</span>
            </div>
            <div v-if="scoreResult" class="score-wrap">
              <div class="score-left">
                <el-progress type="dashboard" :percentage="scoreResult.score" :width="130"
                  :color="levelColor(scoreResult.level)" :stroke-width="12">
                  <template #default><span style="font-size:30px;font-weight:700">{{ scoreResult.score }}</span><div style="font-size:12px;color:#909399">综合得分</div></template>
                </el-progress>
                <div class="level-tag">
                  <el-tag :color="levelColor(scoreResult.level)" effect="dark" style="border:none">{{ scoreResult.level }}</el-tag>
                </div>
              </div>
              <div class="md-body" style="flex:1;min-width:0" v-html="$md(scoreResult.analysis)"></div>
            </div>
            <el-empty v-else-if="!scoring" description="点击「生成评分」获取结构化评分结果" :image-size="80"/>
          </el-tab-pane>

          <!-- 问题分析（SSE） -->
          <el-tab-pane label="问题分析" name="analysis" lazy>
            <div class="ai-toolbar">
              <span class="lbl">模型配置</span>
              <el-select v-model="configId" placeholder="默认（最新启用配置）" style="width:230px" clearable>
                <el-option v-for="c in options.configs" :key="c.id" :label="c.provider + ' · ' + c.model_name" :value="c.id"/>
              </el-select>
              <span class="lbl">Prompt模板</span>
              <el-select v-model="promptSel.analysis" placeholder="默认模板" style="width:250px" clearable>
                <el-option v-for="p in promptsOf('analysis')" :key="p.id" :label="p.name + '（' + p.code + '）'" :value="p.id"/>
              </el-select>
              <el-button type="primary" :loading="streaming.analysis" @click="startStream('analysis')">
                <el-icon><Search/></el-icon>{{ streaming.analysis ? 'AI 正在分析...' : '生成分析' }}
              </el-button>
              <span class="hint">流式输出：核心问题 + 岗位适配分析</span>
            </div>
            <div v-if="streamText.analysis || streaming.analysis" ref="stream-analysis" class="stream-panel md-body"
              :class="{'stream-cursor': streaming.analysis}" v-html="$md(streamText.analysis)"></div>
            <el-empty v-else description="点击「生成分析」，AI 将流式输出简历存在的问题" :image-size="80"/>
          </el-tab-pane>

          <!-- 优化建议（SSE） -->
          <el-tab-pane label="优化建议" name="suggestion" lazy>
            <div class="ai-toolbar">
              <span class="lbl">模型配置</span>
              <el-select v-model="configId" placeholder="默认（最新启用配置）" style="width:230px" clearable>
                <el-option v-for="c in options.configs" :key="c.id" :label="c.provider + ' · ' + c.model_name" :value="c.id"/>
              </el-select>
              <span class="lbl">Prompt模板</span>
              <el-select v-model="promptSel.suggestion" placeholder="默认模板" style="width:250px" clearable>
                <el-option v-for="p in promptsOf('suggestion')" :key="p.id" :label="p.name + '（' + p.code + '）'" :value="p.id"/>
              </el-select>
              <el-button type="primary" :loading="streaming.suggestion" @click="startStream('suggestion')">
                <el-icon><MagicStick/></el-icon>{{ streaming.suggestion ? 'AI 正在生成...' : '生成建议' }}
              </el-button>
              <span class="hint">突出亮点 · 量化成果 · 删减冗余 · 关键词匹配 · 缺口分析</span>
            </div>
            <div v-if="streamText.suggestion || streaming.suggestion" ref="stream-suggestion" class="stream-panel md-body"
              :class="{'stream-cursor': streaming.suggestion}" v-html="$md(streamText.suggestion)"></div>
            <el-empty v-else description="点击「生成建议」，获得可执行的修改建议与岗位适配分析" :image-size="80"/>
          </el-tab-pane>

          <!-- 简历改写（候选 + 采纳） -->
          <el-tab-pane label="简历改写" name="rewrite" lazy>
            <div class="ai-toolbar">
              <span class="lbl">模型配置</span>
              <el-select v-model="configId" placeholder="默认（最新启用配置）" style="width:230px" clearable>
                <el-option v-for="c in options.configs" :key="c.id" :label="c.provider + ' · ' + c.model_name" :value="c.id"/>
              </el-select>
              <span class="lbl">Prompt模板</span>
              <el-select v-model="promptSel.rewrite" placeholder="默认模板" style="width:250px" clearable>
                <el-option v-for="p in promptsOf('rewrite')" :key="p.id" :label="p.name + '（' + p.code + '）'" :value="p.id"/>
              </el-select>
              <el-button type="primary" :loading="streaming.rewrite" @click="startStream('rewrite')">
                <el-icon><Refresh/></el-icon>{{ streaming.rewrite ? 'AI 正在改写...' : '生成改写' }}
              </el-button>
              <span class="hint">生成候选版本，确认后采纳，不会自动覆盖原文</span>
            </div>
            <div class="rewrite-actions" v-if="rewriteRecordId">
              <el-tag type="warning" effect="plain">候选版本已生成，尚未覆盖当前简历</el-tag>
              <el-button type="success" :loading="adopting" @click="adoptRewrite"><el-icon><CircleCheck/></el-icon>采纳为当前简历</el-button>
            </div>
            <div v-if="streamText.rewrite || streaming.rewrite" ref="stream-rewrite" class="stream-panel plain-text"
              :class="{'stream-cursor': streaming.rewrite}">{{ streamText.rewrite }}</div>
            <el-empty v-else description="点击「生成改写」，AI 将输出完整改写简历（轻度润色 / STAR / 专业化三种模板可选）" :image-size="80"/>
          </el-tab-pane>

          <!-- 模拟面试题 -->
          <el-tab-pane label="模拟面试题" name="interview" lazy>
            <div class="ai-toolbar">
              <span class="lbl">模型配置</span>
              <el-select v-model="configId" placeholder="默认（最新启用配置）" style="width:230px" clearable>
                <el-option v-for="c in options.configs" :key="c.id" :label="c.provider + ' · ' + c.model_name" :value="c.id"/>
              </el-select>
              <span class="lbl">Prompt模板</span>
              <el-select v-model="promptSel.interview" placeholder="默认模板" style="width:250px" clearable>
                <el-option v-for="p in promptsOf('interview')" :key="p.id" :label="p.name + '（' + p.code + '）'" :value="p.id"/>
              </el-select>
              <el-button type="primary" :loading="interviewLoading" @click="startInterview">
                <el-icon><ChatDotRound/></el-icon>{{ interviewLoading ? 'AI 正在出题...' : '生成面试题' }}
              </el-button>
              <span class="hint">基于当前简历与目标岗位，生成分类模拟面试题</span>
            </div>
            <template v-if="interview">
              <el-collapse v-model="activeInterview">
                <el-collapse-item v-for="(c, i) in interview" :key="i" :name="i">
                  <template #title><b>{{ c.name }}</b><el-tag size="small" style="margin-left:8px">{{ c.questions.length }} 题</el-tag></template>
                  <div class="interview-cat">
                    <div class="q" v-for="(q, j) in c.questions" :key="j"><span class="no">{{ j + 1 }}</span>{{ q }}</div>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </template>
            <el-empty v-else-if="!interviewLoading" description="点击「生成面试题」开始模拟面试" :image-size="80"/>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>

    <!-- 岗位JD 编辑 -->
    <el-dialog v-model="showJd" title="岗位JD（选填）" width="600px">
      <el-alert type="info" :closable="false" style="margin-bottom:12px"
        title="粘贴目标岗位的职位描述，AI 将据此做岗位关键词匹配与缺口分析"/>
      <el-input v-model="jdForm.job_desc" type="textarea" :rows="8"
        placeholder="如：熟悉 Python/Flask/FastAPI，熟悉 MySQL、Redis，了解消息队列与分布式基础..."/>
      <template #footer>
        <el-button @click="showJd = false">取消</el-button>
        <el-button type="primary" :loading="savingJd" @click="saveJd">保存</el-button>
      </template>
    </el-dialog>
  </div>`,
  data() {
    return {
      resumeOptions: [],
      selectedId: null,
      form: { title: '', target_position: '' },
      current: null, editText: '', saving: false, parsing: false,
      activeTab: 'score',
      showJd: false, savingJd: false, jdForm: { job_desc: '' },
      options: { configs: [], prompts: [] },
      configId: null,
      promptSel: { score: null, analysis: null, suggestion: null, rewrite: null, interview: null },
      scoring: false, scoreResult: null,
      streaming: { analysis: false, suggestion: false, rewrite: false },
      streamText: { analysis: '', suggestion: '', rewrite: '' },
      rewriteRecordId: null, adopting: false,
      interviewLoading: false, interview: null, activeInterview: [0],
    };
  },
  mounted() {
    this.loadResumes();
    this.loadAiOptions();
  },
  methods: {
    levelColor(level) { return LEVEL_COLORS[level] || '#409eff'; },
    promptsOf(scene) { return this.options.prompts.filter((p) => p.scene === scene); },
    async loadResumes() {
      try {
        const d = await api.get('/resumes', { params: { page: 1, page_size: 100 } });
        this.resumeOptions = d.items;
        if (this.current && !d.items.some((x) => x.id === this.current.id)) this.clearCurrent();
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
    },
    async loadAiOptions() {
      try {
        const d = await api.get('/ai/options');
        this.options = d;
        for (const scene of SCENES) {
          if (!this.promptSel[scene]) {
            const first = d.prompts.find((p) => p.scene === scene);
            if (first) this.promptSel[scene] = first.id;
          }
        }
      } catch (e) { /* 选择器加载失败不阻塞主流程 */ }
    },
    async onSelectChange(id) {
      if (Object.values(this.streaming).some(Boolean)) {
        ElementPlus.ElMessage.warning('AI 正在生成中，请等待完成后再切换简历');
        await this.$nextTick();
        this.selectedId = this.current ? this.current.id : null;
        return;
      }
      if (!id) { this.clearCurrent(); return; }
      try {
        const d = await api.get('/resumes/' + id);
        this.applyResume(d);
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
    },
    applyResume(d) {
      this.current = d;
      this.selectedId = d.id;
      this.form.title = d.title;
      this.form.target_position = d.target_position;
      this.editText = d.current_text;
      this.scoreResult = null;
      this.streamText = { analysis: '', suggestion: '', rewrite: '' };
      this.rewriteRecordId = null;
      this.interview = null;
    },
    clearCurrent() {
      this.current = null;
      this.selectedId = null;
      this.form = { title: '', target_position: '' };
      this.editText = '';
      this.scoreResult = null;
      this.streamText = { analysis: '', suggestion: '', rewrite: '' };
      this.rewriteRecordId = null;
      this.interview = null;
    },
    onPickFile(file) {
      if (file && file.raw) this.doUpload(file.raw);
    },
    async doUpload(rawFile) {
      if (!this.form.title.trim()) { ElementPlus.ElMessage.warning('请先填写简历标题'); return; }
      this.parsing = true;
      try {
        let d;
        if (this.current) {
          // 已有简历：更新标题/岗位后重新解析并替换文本
          await api.put('/resumes/' + this.current.id, {
            title: this.form.title, target_position: this.form.target_position,
          });
          const fd = new FormData();
          fd.append('file', rawFile);
          d = await api.post('/resumes/' + this.current.id + '/parse', fd);
        } else {
          const fd = new FormData();
          fd.append('title', this.form.title);
          fd.append('target_position', this.form.target_position);
          fd.append('file', rawFile);
          d = await api.post('/resumes/upload', fd);
        }
        this.applyResume(d);
        await this.loadResumes();
        ElementPlus.ElMessage.success('解析完成，已作为当前版本');
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
      this.parsing = false;
    },
    async saveSilent() {
      if (!this.current) return;
      const body = { title: this.form.title, target_position: this.form.target_position };
      if (this.editText !== this.current.current_text) body.current_text = this.editText;
      if (body.current_text || body.title !== this.current.title || body.target_position !== this.current.target_position) {
        const d = await api.put('/resumes/' + this.current.id, body);
        this.current = d;
      }
    },
    async saveCurrent() {
      if (!this.form.title.trim()) { ElementPlus.ElMessage.warning('请先填写简历标题'); return; }
      if (!this.editText.trim()) { ElementPlus.ElMessage.warning('请先粘贴或编辑简历文本'); return; }
      this.saving = true;
      try {
        if (this.current) {
          const d = await api.put('/resumes/' + this.current.id, {
            title: this.form.title, target_position: this.form.target_position, current_text: this.editText,
          });
          this.current = d;
          ElementPlus.ElMessage.success('已保存当前文本');
        } else {
          const d = await api.post('/resumes', {
            title: this.form.title, target_position: this.form.target_position, text: this.editText,
          });
          this.applyResume(d);
          await this.loadResumes();
          ElementPlus.ElMessage.success('已创建简历并保存');
        }
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
      this.saving = false;
    },
    openJd() {
      this.jdForm.job_desc = this.current ? this.current.job_desc : '';
      this.showJd = true;
    },
    async saveJd() {
      this.savingJd = true;
      try {
        const d = await api.put('/resumes/' + this.current.id, { job_desc: this.jdForm.job_desc });
        this.current = d;
        this.showJd = false;
        ElementPlus.ElMessage.success('岗位JD已保存');
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
      this.savingJd = false;
    },
    async downloadWord() {
      try {
        await authDownload('/api/resumes/' + this.current.id + '/download', this.current.title + '.docx');
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
    },
    async removeResume() {
      try { await ElementPlus.ElMessageBox.confirm('确定删除该简历及其相关 AI 记录吗？', '删除确认', { type: 'warning' }); }
      catch (e) { return; }
      try {
        await api.delete('/resumes/' + this.current.id);
        this.clearCurrent();
        await this.loadResumes();
        ElementPlus.ElMessage.success('已删除');
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
    },
    optsBody(scene) {
      return { config_id: this.configId || null, prompt_id: this.promptSel[scene] || null };
    },
    async startScore() {
      if (!this.current) { ElementPlus.ElMessage.warning('请先选择或上传简历'); return; }
      this.scoring = true;
      this.scoreResult = null;
      try {
        await this.saveSilent();
        this.scoreResult = await api.post('/ai/resumes/' + this.current.id + '/score', this.optsBody('score'));
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
      this.scoring = false;
    },
    startStream(kind) {
      if (!this.current) { ElementPlus.ElMessage.warning('请先选择或上传简历'); return; }
      if (this.streaming[kind]) return;
      const self = this;
      this.streaming[kind] = true;
      this.streamText[kind] = '';
      if (kind === 'rewrite') this.rewriteRecordId = null;
      this.saveSilent()
        .then(() => streamSSE('/api/ai/resumes/' + self.current.id + '/' + kind, self.optsBody(kind), {
          onDelta(d) {
            self.streamText[kind] += d;
            self.$nextTick(() => {
              const el = self.$refs['stream-' + kind];
              if (el) el.scrollTop = el.scrollHeight;
            });
          },
          onDone(evt) { if (kind === 'rewrite') self.rewriteRecordId = evt.record_id; },
          onError(msg) { ElementPlus.ElMessage.error(msg); },
        }))
        .catch((e) => ElementPlus.ElMessage.error(e.message))
        .finally(() => { self.streaming[kind] = false; });
    },
    async adoptRewrite() {
      try { await ElementPlus.ElMessageBox.confirm('采纳后将以改写内容覆盖「简历文本」，是否继续？', '采纳确认', { type: 'warning', confirmButtonText: '确认采纳' }); }
      catch (e) { return; }
      this.adopting = true;
      try {
        const d = await api.post('/ai/rewrite/adopt', { history_id: this.rewriteRecordId });
        this.applyResume(d.resume);
        await this.loadResumes();
        ElementPlus.ElMessage.success('已采纳改写结果，当前简历已更新');
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
      this.adopting = false;
    },
    async startInterview() {
      if (!this.current) { ElementPlus.ElMessage.warning('请先选择或上传简历'); return; }
      this.interviewLoading = true;
      this.interview = null;
      try {
        await this.saveSilent();
        const d = await api.post('/ai/resumes/' + this.current.id + '/interview', this.optsBody('interview'));
        this.interview = d.categories;
        this.activeInterview = [0];
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
      this.interviewLoading = false;
    },
  },
};
