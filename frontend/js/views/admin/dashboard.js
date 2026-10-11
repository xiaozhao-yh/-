/* 管理端：系统首页（数据看板 + AI 调用概况） */
/* global Vue, api, echarts, fmtTime, fmtDuration, TYPE_MAP, TYPE_COLORS */

const AdminDashboard = {
  template: `
  <div>
    <div class="stat-cards">
      <div class="stat-card">
        <div class="icon" style="background:linear-gradient(135deg,#409eff,#2a5298)"><el-icon><UserFilled/></el-icon></div>
        <div><div class="num">{{ stat.user_count }}</div><div class="label">普通用户数（总 {{ stat.total_user_count }}）</div></div>
      </div>
      <div class="stat-card">
        <div class="icon" style="background:linear-gradient(135deg,#67c23a,#4f9e26)"><el-icon><Files/></el-icon></div>
        <div><div class="num">{{ stat.resume_count }}</div><div class="label">简历总数</div></div>
      </div>
      <div class="stat-card">
        <div class="icon" style="background:linear-gradient(135deg,#e6a23c,#c8821e)"><el-icon><MagicStick/></el-icon></div>
        <div><div class="num">{{ stat.ai_call_count }}</div><div class="label">AI 调用总次数</div></div>
      </div>
      <div class="stat-card">
        <div class="icon" style="background:linear-gradient(135deg,#f56c6c,#d63d3d)"><el-icon><TrendCharts/></el-icon></div>
        <div><div class="num">{{ stat.today_calls }}</div><div class="label">今日 AI 调用</div></div>
      </div>
    </div>

    <div class="chart-row">
      <div class="chart-box"><div class="chart-title">近 7 天 AI 调用趋势</div><div ref="trend" class="chart"></div></div>
      <div class="chart-box"><div class="chart-title">AI 场景调用分布</div><div ref="pie" class="chart"></div></div>
    </div>

    <div class="chart-box">
      <div class="chart-title">模型调用统计</div>
      <el-table :data="stat.model_stats" size="small" style="max-width:520px">
        <el-table-column prop="name" label="模型"/>
        <el-table-column prop="value" label="调用次数" width="120"/>
      </el-table>
    </div>

    <div class="page-card" style="margin-top:14px">
      <div class="chart-title" style="margin-bottom:10px">最近 AI 调用记录</div>
      <el-table :data="stat.recent" size="small">
        <el-table-column prop="username" label="用户" width="110"/>
        <el-table-column prop="resume_title" label="简历标题" min-width="150" show-overflow-tooltip/>
        <el-table-column label="类型" width="110">
          <template #default="{row}"><el-tag :type="typeColors[row.type]" size="small">{{ typeMap[row.type] || row.type }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="model" label="模型" width="130" show-overflow-tooltip/>
        <el-table-column label="耗时" width="80">
          <template #default="{row}">{{ fmtDur(row.duration_ms) }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="170"/>
      </el-table>
    </div>
  </div>`,
  data() {
    return { stat: { user_count: 0, total_user_count: 0, resume_count: 0, ai_call_count: 0, today_calls: 0,
      type_stats: [], model_stats: [], trend: [], recent: [] },
      typeMap: TYPE_MAP, typeColors: TYPE_COLORS };
  },
  mounted() { this.load(); window.addEventListener('resize', this.onResize); },
  beforeUnmount() { window.removeEventListener('resize', this.onResize); },
  methods: {
    fmtDur: fmtDuration,
    fmt: fmtTime,
    onResize() {
      if (this.trendChart) this.trendChart.resize();
      if (this.pieChart) this.pieChart.resize();
    },
    async load() {
      try {
        const d = await api.get('/admin/dashboard');
        this.stat = d;
        this.$nextTick(() => this.renderCharts(d));
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
    },
    renderCharts(d) {
      const names = Object.assign({}, TYPE_MAP);
      this.trendChart = echarts.init(this.$refs.trend);
      this.trendChart.setOption({
        tooltip: { trigger: 'axis' },
        grid: { left: 40, right: 20, top: 30, bottom: 30 },
        xAxis: { type: 'category', data: d.trend.map((t) => t.date) },
        yAxis: { type: 'value', minInterval: 1 },
        series: [{ data: d.trend.map((t) => t.count), type: 'line', smooth: true, areaStyle: { opacity: 0.15 },
          itemStyle: { color: '#2a5298' }, name: 'AI 调用次数' }],
      });
      this.pieChart = echarts.init(this.$refs.pie);
      this.pieChart.setOption({
        tooltip: { trigger: 'item' },
        legend: { bottom: 0, itemWidth: 12, itemHeight: 12 },
        series: [{
          type: 'pie', radius: ['42%', '68%'], center: ['50%', '44%'],
          label: { formatter: '{b}: {c}' },
          data: d.type_stats.map((t) => ({ name: names[t.name] || t.name, value: t.value })),
        }],
      });
    },
  },
};
