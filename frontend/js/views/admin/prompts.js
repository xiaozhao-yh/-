/* 管理端：Prompt 模板管理（表格 CRUD：搜索/筛选/新增/编辑/删除/批量删除/状态） */
/* global Vue, api, fmtTime, SCENE_MAP, ElementPlus */

const AdminPrompts = {
  template: `
  <div class="page-card">
    <div class="table-toolbar">
      <el-input v-model="q.name" placeholder="模板名称" style="width:180px" clearable @keyup.enter="doSearch"/>
      <el-input v-model="q.code" placeholder="模板编码" style="width:180px" clearable @keyup.enter="doSearch"/>
      <el-select v-model="q.scene" placeholder="适用场景" style="width:150px" clearable>
        <el-option v-for="(label, key) in sceneMap" :key="key" :label="label" :value="key"/>
      </el-select>
      <el-button type="primary" plain @click="doSearch"><el-icon><Search/></el-icon>查询</el-button>
      <el-button type="primary" @click="openCreate"><el-icon><Plus/></el-icon>新增</el-button>
      <el-button type="danger" plain :disabled="!selection.length" @click="batchDelete">
        <el-icon><Delete/></el-icon>批量删除{{ selection.length ? '（' + selection.length + '）' : '' }}
      </el-button>
    </div>

    <el-table :data="items" v-loading="loading" @selection-change="onSel" row-key="id" border>
      <el-table-column type="selection" width="44"/>
      <el-table-column prop="name" label="模板名称" min-width="150" show-overflow-tooltip/>
      <el-table-column prop="code" label="模板编码" min-width="170">
        <template #default="{ row }"><el-tag size="small" effect="plain">{{ row.code }}</el-tag></template>
      </el-table-column>
      <el-table-column label="适用场景" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="typeColor(row.scene)">{{ sceneMap[row.scene] || row.scene }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="content" label="Prompt内容" min-width="240">
        <template #default="{ row }"><span class="prompt-preview">{{ row.content }}</span></template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-switch :model-value="row.status" @change="toggleStatus(row)"/>
        </template>
      </el-table-column>
      <el-table-column prop="updated_at" label="更新时间" width="165"/>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)"><el-icon><Edit/></el-icon>编辑</el-button>
          <el-button link type="danger" @click="removeOne(row)"><el-icon><Delete/></el-icon>删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination background layout="total, prev, pager, next, sizes" :total="total"
        v-model:current-page="page" v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50]" @change="load"/>
    </div>

    <el-dialog v-model="dialog" :title="editing ? '编辑模板' : '新增模板'" width="760px" top="6vh">
      <el-form label-width="90px">
        <el-form-item label="模板编码" required>
          <el-input v-model="form.code" placeholder="大写下划线，如 RESUME_REWRITE_STAR" maxlength="50" :disabled="false"/>
        </el-form-item>
        <el-form-item label="模板名称" required>
          <el-input v-model="form.name" placeholder="如：STAR项目改写模板" maxlength="50"/>
        </el-form-item>
        <el-form-item label="适用场景" required>
          <el-select v-model="form.scene" style="width:100%">
            <el-option v-for="(label, key) in sceneMap" :key="key" :label="label + '（' + key + '）'" :value="key"/>
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" active-text="启用" inactive-text="停用"/>
        </el-form-item>
        <el-form-item label="Prompt内容" required>
          <el-input v-model="form.content" type="textarea" :rows="16" style="font-family:Consolas,monospace"
            placeholder="支持占位符：{resume_text} 简历文本、{target_position} 目标岗位、{job_desc} 岗位JD"/>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>`,
  data() {
    return {
      sceneMap: SCENE_MAP,
      items: [], total: 0, page: 1, pageSize: 10, loading: false, loadSeq: 0,
      q: { name: '', code: '', scene: '' },
      selection: [],
      dialog: false, editing: null, saving: false,
      form: { code: '', name: '', scene: 'score', content: '', status: true },
    };
  },
  mounted() { this.load(); },
  methods: {
    typeColor(scene) { return { score: '', analysis: 'warning', suggestion: 'success', rewrite: 'danger', interview: 'info' }[scene] || ''; },
    onSel(rows) { this.selection = rows; },
    doSearch() { this.page = 1; this.load(); },
    async load() {
      const seq = ++this.loadSeq;   // 序号守卫：丢弃过期响应
      this.loading = true;
      try {
        const d = await api.get('/admin/prompts', {
          params: { page: this.page, page_size: this.pageSize, name: this.q.name, code: this.q.code, scene: this.q.scene },
        });
        if (seq !== this.loadSeq) return;
        if (!d.items.length && this.page > 1 && d.total > 0) {   // 页码越界回退
          this.page = Math.max(1, Math.ceil(d.total / this.pageSize));
          this.loading = false;
          return this.load();
        }
        this.items = d.items;
        this.total = d.total;
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
      if (seq === this.loadSeq) this.loading = false;
    },
    openCreate() {
      this.editing = null;
      this.form = { code: '', name: '', scene: 'score', content: '', status: true };
      this.dialog = true;
    },
    openEdit(p) {
      this.editing = p;
      this.form = { code: p.code, name: p.name, scene: p.scene, content: p.content, status: p.status };
      this.dialog = true;
    },
    async save() {
      if (!this.form.code.trim()) { ElementPlus.ElMessage.warning('请填写模板编码'); return; }
      if (!this.form.name.trim()) { ElementPlus.ElMessage.warning('请填写模板名称'); return; }
      if (!this.form.content.trim()) { ElementPlus.ElMessage.warning('请填写 Prompt 内容'); return; }
      this.saving = true;
      try {
        if (this.editing) {
          await api.put('/admin/prompts/' + this.editing.id, this.form);
          ElementPlus.ElMessage.success('模板已保存并生效');
        } else {
          await api.post('/admin/prompts', this.form);
          ElementPlus.ElMessage.success('模板已创建');
        }
        this.dialog = false;
        this.load();
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
      this.saving = false;
    },
    async toggleStatus(row) {
      try {
        await api.put('/admin/prompts/' + row.id, { status: !row.status });
        row.status = !row.status;
        ElementPlus.ElMessage.success(row.status ? '已启用' : '已停用');
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
    },
    async removeOne(row) {
      try { await ElementPlus.ElMessageBox.confirm(`确定删除模板「${row.name}（${row.code}）」吗？`, '删除确认', { type: 'warning' }); }
      catch (e) { return; }
      try {
        await api.delete('/admin/prompts/' + row.id);
        ElementPlus.ElMessage.success('已删除');
        this.load();
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
    },
    async batchDelete() {
      try { await ElementPlus.ElMessageBox.confirm(`确定删除选中的 ${this.selection.length} 个模板吗？`, '批量删除确认', { type: 'warning' }); }
      catch (e) { return; }
      try {
        await api.post('/admin/prompts/batch-delete', { ids: this.selection.map((r) => r.id) });
        ElementPlus.ElMessage.success('批量删除成功');
        this.load();
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
    },
  },
};
