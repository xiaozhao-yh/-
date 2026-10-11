/* 管理端：用户信息管理（新增/编辑/删除/分页/头像） */
/* global Vue, api, fmtTime, ElementPlus */

const AdminUsers = {
  template: `
  <div class="page-card">
    <div class="table-toolbar">
      <el-input v-model="keyword" placeholder="搜索用户名 / 昵称 / 邮箱" clearable style="width:260px" @input="searchNow">
        <template #prefix><el-icon><Search/></el-icon></template>
      </el-input>
      <el-button type="primary" @click="openCreate"><el-icon><Plus/></el-icon>新增用户</el-button>
      <div class="grow"></div>
      <span style="color:#909399;font-size:13px">共 {{ total }} 个用户</span>
    </div>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70"/>
      <el-table-column label="头像" width="70">
        <template #default="{row}">
          <el-avatar :size="36" :src="row.avatar ? API_BASE + row.avatar : ''">
            <el-icon><UserFilled/></el-icon>
          </el-avatar>
        </template>
      </el-table-column>
      <el-table-column prop="username" label="用户名" width="130"/>
      <el-table-column prop="nickname" label="昵称" width="130" show-overflow-tooltip/>
      <el-table-column prop="email" label="邮箱" min-width="160" show-overflow-tooltip/>
      <el-table-column prop="phone" label="手机号" width="130"/>
      <el-table-column label="角色" width="100">
        <template #default="{row}"><el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">{{ row.role === 'admin' ? '管理员' : '用户' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="注册时间" width="170">
        <template #default="{row}">{{ fmt(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{row}">
          <el-button size="small" text type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" text type="danger" @click="removeUser(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="pager"><el-pagination background layout="total, prev, pager, next, sizes" :total="total"
      v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[10, 20, 50]" @change="load"/></div>

    <el-dialog v-model="dialog" :title="editing ? '编辑用户' : '新增用户'" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" :disabled="editing" maxlength="30"/>
        </el-form-item>
        <el-form-item :label="editing ? '重置密码' : '密码'" :required="!editing">
          <el-input v-model="form.password" type="password" show-password
            :placeholder="editing ? '留空表示不修改密码' : '至少6位'"/>
        </el-form-item>
        <el-form-item label="昵称"><el-input v-model="form.nickname" maxlength="30"/></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="form.email"/></el-form-item>
        <el-form-item label="手机号"><el-input v-model="form.phone"/></el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="form.role">
            <el-radio value="user">普通用户</el-radio>
            <el-radio value="admin">管理员</el-radio>
          </el-radio-group>
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
      API_BASE: window.API_BASE,
      items: [], total: 0, page: 1, pageSize: 10, keyword: '', loading: false, searchTimer: null,
      dialog: false, editing: false, editingId: null, saving: false,
      form: { username: '', password: '', nickname: '', email: '', phone: '', role: 'user' },
    };
  },
  mounted() { this.load(); },
  methods: {
    fmt: fmtTime,
    searchNow() {
      clearTimeout(this.searchTimer);
      this.searchTimer = setTimeout(() => { this.page = 1; this.load(); }, 300);
    },
    async load() {
      this.loading = true;
      try {
        const d = await api.get('/admin/users', { params: { page: this.page, page_size: this.pageSize, keyword: this.keyword } });
        this.items = d.items;
        this.total = d.total;
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
      this.loading = false;
    },
    openCreate() {
      this.editing = false;
      this.form = { username: '', password: '', nickname: '', email: '', phone: '', role: 'user' };
      this.dialog = true;
    },
    openEdit(row) {
      this.editing = true;
      this.editingId = row.id;
      this.form = { username: row.username, password: '', nickname: row.nickname, email: row.email, phone: row.phone, role: row.role };
      this.dialog = true;
    },
    async save() {
      if (!this.form.username.trim()) { ElementPlus.ElMessage.warning('请填写用户名'); return; }
      if (!this.editing && this.form.password.length < 6) { ElementPlus.ElMessage.warning('密码至少 6 位'); return; }
      this.saving = true;
      try {
        if (this.editing) await api.put('/admin/users/' + this.editingId, this.form);
        else await api.post('/admin/users', this.form);
        ElementPlus.ElMessage.success('已保存');
        this.dialog = false;
        this.load();
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
      this.saving = false;
    },
    async removeUser(row) {
      try { await ElementPlus.ElMessageBox.confirm('确定删除用户「' + row.username + '」吗？其简历与 AI 记录将一并删除。', '删除确认', { type: 'warning' }); }
      catch (e) { return; }
      try {
        await api.delete('/admin/users/' + row.id);
        ElementPlus.ElMessage.success('已删除');
        this.load();
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
    },
  },
};
