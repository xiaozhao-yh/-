/* 管理端：AI 历史记录（按用户/简历标题/模型/Prompt编码/类型筛选 + 详情） */
/* global Vue, api, fmtTime, fmtDuration, TYPE_MAP, TYPE_COLORS */

const AdminHistory = {
  template: `
  <div class="page-card">
    <div class="table-toolbar">
      <el-select v-model="filters.user_id" placeholder="全部用户" clearable filterable style="width:170px" @change="search">
        <el-option v-for="u in users" :key="u.id" :label="u.username + (u.nickname ? ' / ' + u.nickname : '')" :value="u.id"/>
      </el-select>
      <el-input v-model="filters.resume_title" placeholder="简历标题" clearable style="width:180px" @input="searchNow"/>
      <el-input v-model="filters.model" placeholder="模型" clearable style="width:150px" @input="searchNow"/>
      <el-select v-model="filters.type" placeholder="记录类型" clearable style="width:140px" @change="search">
        <el-option v-for="(name, key) in typeMap" :key="key" :label="name" :value="key"/>
      </el-select>
      <el-button @click="search"><el-icon><Refresh/></el-icon>查询</el-button>
      <div class="grow"></div>
      <span style="color:#909399;font-size:13px">共 {{ total }} 条记录</span>
    </div>
    <el-table :data="items" v-loading="loading" stripe height="520">
      <el-table-column prop="id" label="ID" width="70"/>
      <el-table-column prop="username" label="用户" width="110"/>
      <el-table-column prop="resume_title" label="简历标题" min-width="150" show-overflow-tooltip/>
      <el-table-column label="类型" width="110">
        <template #default="{row}"><el-tag :type="typeColors[row.type]" size="small">{{ typeMap[row.type] || row.type }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="model" label="模型" width="130" show-overflow-tooltip/>
      <el-table-column label="得分" min-width="140">
        <template #default="{row}">
          <template v-if="row.score !== null && row.score !== undefined">
            <span class="score-num">{{ row.score }} 分</span>
            <el-tag size="small" :type="levelType(row.level)">{{ row.level }}</el-tag>
          </template>
          <span v-else style="color:#c0c4cc">-</span>
        </template>
      </el-table-column>
      <el-table-column label="耗时" width="80">
        <template #default="{row}">{{ fmtDur(row.duration_ms) }}</template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" width="170"/>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{row}"><el-button size="small" text type="primary" @click="showDetail(row.id)">详情</el-button></template>
      </el-table-column>
    </el-table>
    <div class="pager"><el-pagination background layout="total, prev, pager, next, sizes" :total="total"
      v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[10, 20, 50]" @change="load"/></div>

    <el-drawer v-model="drawer" title="AI 调用完整详情" size="56%">
      <template v-if="detail">
        <el-descriptions :column="2" border size="small" style="margin-bottom:14px">
          <el-descriptions-item label="用户">{{ detail.username }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ typeMap[detail.type] || detail.type }}</el-descriptions-item>
          <el-descriptions-item label="模型">{{ detail.model }}</el-descriptions-item>
          <el-descriptions-item label="Prompt 编码">{{ detail.prompt_code }}</el-descriptions-item>
          <el-descriptions-item label="简历">{{ detail.resume_title || '-' }}</el-descriptions-item>
          <el-descriptions-item label="耗时 / 时间">{{ fmtDur(detail.duration_ms) }} / {{ detail.created_at }}</el-descriptions-item>
        </el-descriptions>
        <h4 style="margin:8px 0">输入</h4>
        <pre class="detail-pre">{{ detail.input_text }}</pre>
        <h4 style="margin:14px 0 8px">输出结果</h4>
        <div v-if="isMd" class="md-body stream-panel" v-html="$md(detail.output_text)"></div>
        <pre v-else class="detail-pre" style="max-height:none">{{ prettyOutput }}</pre>
      </template>
    </el-drawer>
  </div>`,
  data() {
    return {
      typeMap: TYPE_MAP, typeColors: TYPE_COLORS,
      users: [],
      items: [], total: 0, page: 1, pageSize: 10, loading: false, searchTimer: null, loadSeq: 0,
      filters: { user_id: null, resume_title: '', model: '', type: '' },
      drawer: false, detail: null,
    };
  },
  computed: {
    isMd() { return this.detail && ['analysis', 'suggestion', 'rewrite'].includes(this.detail.type); },
    prettyOutput() {
      if (!this.detail) return '';
      try { return JSON.stringify(JSON.parse(this.detail.output_text), null, 2); }
      catch (e) { return this.detail.output_text; }
    },
  },
  mounted() { this.load(); this.loadUsers(); },
  methods: {
    fmt: fmtTime,
    fmtDur: fmtDuration,
    levelType(level) {
      return ({ '优秀': 'success', '良好': 'primary', '合格': 'warning', '待改进': 'danger' })[level] || 'info';
    },
    searchNow() {
      clearTimeout(this.searchTimer);
      this.searchTimer = setTimeout(() => { this.page = 1; this.load(); }, 300);
    },
    search() { this.page = 1; this.load(); },
    async loadUsers() {
      try { this.users = await api.get('/admin/users-all'); }
      catch (e) { /* ignore */ }
    },
    async load() {
      const seq = ++this.loadSeq;   // 序号守卫：丢弃过期响应
      this.loading = true;
      try {
        const params = Object.assign({ page: this.page, page_size: this.pageSize }, this.filters);
        const d = await api.get('/admin/ai-histories', { params });
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
    async showDetail(id) {
      try {
        this.detail = await api.get('/admin/ai-histories/' + id);
        this.drawer = true;
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
    },
  },
};
