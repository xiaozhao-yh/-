/* 管理端：AI 模型配置（服务商/接口地址/API Key/模型名称/启用状态） */
/* global Vue, api, fmtTime, ElementPlus */

const AdminModels = {
  template: `
  <div class="page-card">
    <el-alert type="info" :closable="false" style="margin-bottom:14px"
      title="AI 功能使用「已启用」的最新一条配置（OpenAI 兼容接口，如阿里云百炼 DashScope）。切换模型或修改 Key 无需改动业务代码。"/>
    <div class="table-toolbar">
      <el-button type="primary" @click="openCreate"><el-icon><Plus/></el-icon>新增配置</el-button>
      <el-button @click="load"><el-icon><Refresh/></el-icon>刷新</el-button>
    </div>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60"/>
      <el-table-column prop="provider" label="服务商" width="170" show-overflow-tooltip/>
      <el-table-column prop="base_url" label="接口地址" min-width="240" show-overflow-tooltip/>
      <el-table-column prop="model_name" label="模型名称" width="130"/>
      <el-table-column prop="api_key" label="API Key" width="180" show-overflow-tooltip/>
      <el-table-column label="启用状态" width="100">
        <template #default="{row}">
          <el-switch :model-value="row.is_enabled" @change="toggle(row)"/>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="{row}">{{ fmt(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="130" fixed="right">
        <template #default="{row}">
          <el-button size="small" text type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" text type="danger" @click="removeCfg(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog" :title="editing ? '编辑配置' : '新增配置'" width="560px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="服务商"><el-input v-model="form.provider" placeholder="如：阿里云百炼 DashScope"/></el-form-item>
        <el-form-item label="接口地址" required>
          <el-input v-model="form.base_url" placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1"/>
        </el-form-item>
        <el-form-item label="API Key" required>
          <el-input v-model="form.api_key" :placeholder="editing ? '留空或保持脱敏值则不修改' : 'sk-...'" show-password/>
        </el-form-item>
        <el-form-item label="模型名称" required>
          <el-input v-model="form.model_name" placeholder="如：qwen-plus / qwen-max / deepseek-chat"/>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" maxlength="100"/></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>`,
  data() {
    return {
      items: [], loading: false, dialog: false, editing: false, editingId: null, saving: false,
      form: { provider: '阿里云百炼 DashScope', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', api_key: '', model_name: 'qwen-plus', remark: '' },
    };
  },
  mounted() { this.load(); },
  methods: {
    fmt: fmtTime,
    async load() {
      this.loading = true;
      try { this.items = await api.get('/admin/ai-configs'); }
      catch (e) { ElementPlus.ElMessage.error(e.message); }
      this.loading = false;
    },
    openCreate() {
      this.editing = false;
      this.form = { provider: '阿里云百炼 DashScope', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', api_key: '', model_name: 'qwen-plus', remark: '' };
      this.dialog = true;
    },
    openEdit(row) {
      this.editing = true;
      this.editingId = row.id;
      this.form = { provider: row.provider, base_url: row.base_url, api_key: row.api_key, model_name: row.model_name, remark: row.remark };
      this.dialog = true;
    },
    async save() {
      if (!this.form.base_url.trim() || !this.form.model_name.trim()) { ElementPlus.ElMessage.warning('请填写接口地址与模型名称'); return; }
      if (!this.editing && !this.form.api_key.trim()) { ElementPlus.ElMessage.warning('请填写 API Key'); return; }
      this.saving = true;
      try {
        if (this.editing) await api.put('/admin/ai-configs/' + this.editingId, this.form);
        else await api.post('/admin/ai-configs', this.form);
        ElementPlus.ElMessage.success('已保存（新配置默认未启用，可手动开启）');
        this.dialog = false;
        this.load();
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
      this.saving = false;
    },
    async toggle(row) {
      try {
        const d = await api.post('/admin/ai-configs/' + row.id + '/toggle');
        row.is_enabled = d.is_enabled;
        ElementPlus.ElMessage.success(d.is_enabled ? '已启用' : '已停用');
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
    },
    async removeCfg(row) {
      try { await ElementPlus.ElMessageBox.confirm('确定删除该模型配置吗？', '删除确认', { type: 'warning' }); }
      catch (e) { return; }
      try {
        await api.delete('/admin/ai-configs/' + row.id);
        ElementPlus.ElMessage.success('已删除');
        this.load();
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
    },
  },
};
