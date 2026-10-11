/* 布局组件：用户端 / 管理端 */
/* global Vue, API_BASE, getStoredUser, clearStoredLogin */

const UserLayout = {
  template: `
  <el-container style="height:100%">
    <el-aside :width="isMobile ? '64px' : '220px'" class="app-aside">
      <div class="logo"><el-icon :size="20"><MagicStick/></el-icon><span class="logo-text">AI 简历优化助手</span></div>
      <el-menu router :default-active="$route.path" :collapse="isMobile" :collapse-transition="false"
        background-color="#1f2d3d" text-color="#bfcbd9" active-text-color="#ffffff">
        <el-menu-item index="/workbench"><el-icon><EditPen/></el-icon><span>简历优化工作台</span></el-menu-item>
        <el-menu-item index="/history"><el-icon><Clock/></el-icon><span>AI 历史记录</span></el-menu-item>
        <el-menu-item index="/profile"><el-icon><User/></el-icon><span>个人中心</span></el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header height="60px" class="app-header">
        <div class="header-title">{{ pageTitle }}</div>
        <el-dropdown @command="onCmd">
          <span style="display:flex;align-items:center;gap:8px;cursor:pointer">
            <el-avatar :size="32" :src="avatarUrl" v-if="user && user.avatar"></el-avatar>
            <el-avatar :size="32" v-else><el-icon><UserFilled/></el-icon></el-avatar>
            <span>{{ user ? (user.nickname || user.username) : '' }}</span>
            <el-icon><ArrowDown/></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">个人中心</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出系统</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main class="app-main"><router-view /></el-main>
    </el-container>
  </el-container>`,
  data() { return { isMobile: window.innerWidth < 992 }; },
  computed: {
    user() { return getStoredUser(); },
    avatarUrl() { return this.user && this.user.avatar ? API_BASE + this.user.avatar : ''; },
    pageTitle() {
      const m = { '/workbench': '简历优化工作台', '/history': 'AI 历史记录', '/profile': '个人中心' };
      return m[this.$route.path] || '';
    },
  },
  mounted() { window.addEventListener('resize', this.onResize); },
  beforeUnmount() { window.removeEventListener('resize', this.onResize); },
  methods: {
    onResize() { this.isMobile = window.innerWidth < 992; },
    onCmd(c) {
      if (c === 'profile') this.$router.push('/profile');
      if (c === 'logout') { clearStoredLogin(); this.$router.push('/login'); }
    },
  },
};

const AdminLayout = {
  template: `
  <el-container style="height:100%">
    <el-aside :width="isMobile ? '64px' : '220px'" class="app-aside">
      <div class="logo"><el-icon :size="20"><Setting/></el-icon><span class="logo-text">AI 简历优化助手</span></div>
      <el-menu :router="false" :default-active="$route.path" :collapse="isMobile" :collapse-transition="false" @select="onMenu"
        background-color="#1f2d3d" text-color="#bfcbd9" active-text-color="#ffffff">
        <el-menu-item index="/admin/dashboard"><el-icon><DataBoard/></el-icon><span>系统首页</span></el-menu-item>
        <el-menu-item index="/admin/users"><el-icon><UserFilled/></el-icon><span>用户管理</span></el-menu-item>
        <el-menu-item index="/admin/history"><el-icon><Document/></el-icon><span>AI历史记录</span></el-menu-item>
        <el-menu-item index="/admin/models"><el-icon><Cpu/></el-icon><span>模型配置</span></el-menu-item>
        <el-menu-item index="/admin/prompts"><el-icon><Collection/></el-icon><span>Prompt模板</span></el-menu-item>
        <el-menu-item index="logout" class="logout-item"><el-icon><SwitchButton/></el-icon><span>退出系统</span></el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header height="60px" class="app-header">
        <div class="header-title">{{ pageTitle }}</div>
        <el-dropdown @command="onCmd">
          <span style="display:flex;align-items:center;gap:8px;cursor:pointer">
            <el-avatar :size="32" :src="avatarUrl" v-if="user && user.avatar"></el-avatar>
            <el-avatar :size="32" v-else><el-icon><UserFilled/></el-icon></el-avatar>
            <span>{{ user ? (user.nickname || user.username) : '' }}</span>
            <el-icon><ArrowDown/></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">个人中心</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出系统</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main class="app-main"><router-view /></el-main>
    </el-container>
  </el-container>`,
  data() { return { isMobile: window.innerWidth < 992 }; },
  computed: {
    user() { return getStoredUser(); },
    avatarUrl() { return this.user && this.user.avatar ? API_BASE + this.user.avatar : ''; },
    pageTitle() {
      const m = { '/admin/dashboard': '系统首页', '/admin/users': '用户管理', '/admin/models': '模型配置',
        '/admin/prompts': 'Prompt模板', '/admin/history': 'AI历史记录' };
      return m[this.$route.path] || '';
    },
  },
  mounted() { window.addEventListener('resize', this.onResize); },
  beforeUnmount() { window.removeEventListener('resize', this.onResize); },
  methods: {
    onResize() { this.isMobile = window.innerWidth < 992; },
    onMenu(index) {
      if (index === 'logout') { clearStoredLogin(); this.$router.push('/login'); return; }
      if (index !== this.$route.path) this.$router.push(index);
    },
    onCmd(c) {
      if (c === 'profile') this.$router.push('/profile');
      if (c === 'logout') { clearStoredLogin(); this.$router.push('/login'); }
    },
  },
};
