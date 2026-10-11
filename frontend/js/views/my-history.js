/* 用户端：AI 历史记录 */
/* global Vue, api, fmtTime, fmtDuration, TYPE_MAP, TYPE_COLORS */

const MyHistory = {
  template: `
  <div class="page-card">
    <div class="table-toolbar">
      <el-select v-model="type" placeholder="全部类型" clearable style="width:150px" @change="load">
        <el-option v-for="(name, key) in typeMap" :key="key" :label="name" :value="key"/>
      </el-select>
      <el-button @click="load"><el-icon><Refresh/></el-icon>刷新</el-button>
      <div class="grow"></div>
      <span style="color:#909399;font-size:13px">共 {{ total }} 条 AI 调用记录</span>
    </div>
    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column label="类型" width="110">
        <template #default="{row}"><el-tag :type="typeColors[row.type]" size="small">{{ typeMap[row.type] || row.type }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="resume_title" label="简历标题" min-width="160" show-overflow-tooltip/>
      <el-table-column prop="model" label="模型" width="120" show-overflow-tooltip/>
      <el-table-column label="得分" width="90">
        <template #default="{row}">
          <span v-if="row.score !== null && row.score !== undefined">{{ row.score }} 分 / {{ row.level }}</span>
          <span v-else style="color:#c0c4cc">-</span>
        </template>
      </el-table-column>
      <el-table-column label="耗时" width="80">
        <template #default="{row}">{{ fmtDur(row.duration_ms) }}</template>
      </el-table-column>
      <el-table-column label="时间" width="160">
        <template #default="{row}">{{ fmt(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{row}"><el-button size="small" text type="primary" @click="showDetail(row)">详情</el-button></template>
      </el-table-column>
    </el-table>
    <div class="pager"><el-pagination background layout="total, prev, pager, next, sizes" :total="total"
      v-model:current-page="page" v-model:page-size="pageSize" :page-sizes="[10, 20, 50]" @change="load"/></div>

    <el-drawer v-model="drawer" title="AI 调用详情" size="52%">
      <template v-if="detail">
        <el-descriptions :column="2" border size="small" style="margin-bottom:14px">
          <el-descriptions-item label="类型">{{ typeMap[detail.type] || detail.type }}</el-descriptions-item>
          <el-descriptions-item label="模型">{{ detail.model }}</el-descriptions-item>
          <el-descriptions-item label="简历">{{ detail.resume_title || '-' }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ fmtDur(detail.duration_ms) }}</el-descriptions-item>
        </el-descriptions>
        <h4 style="margin:8px 0">输入摘要</h4>
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
      items: [], total: 0, page: 1, pageSize: 10, type: '', loading: false,
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
  mounted() { this.load(); },
  methods: {
    fmt: fmtTime,
    fmtDur: fmtDuration,
    async load() {
      this.loading = true;
      try {
        const d = await api.get('/ai/histories', { params: { page: this.page, page_size: this.pageSize, type: this.type } });
        this.items = d.items;
        this.total = d.total;
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
      this.loading = false;
    },
    showDetail(row) {
      this.detail = row;
      this.drawer = true;
    },
  },
};
