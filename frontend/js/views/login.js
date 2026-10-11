/* 登录 / 注册 */
/* global Vue, api, setStoredLogin */

const Login = {
  template: `
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo"><el-icon><MagicStick/></el-icon></div>
      <div class="login-title">AI 简历优化助手</div>
      <div class="login-sub">AI 诊断评分 · 问题分析 · 优化建议 · 简历改写 · 模拟面试</div>
      <el-tabs v-model="tab" stretch>
        <el-tab-pane label="登录" name="login">
          <el-form :model="loginForm" :rules="loginRules" ref="loginRef" @keyup.enter="doLogin">
            <el-form-item prop="username">
              <el-input v-model="loginForm.username" placeholder="用户名" size="large">
                <template #prefix><el-icon><User/></el-icon></template>
              </el-input>
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="loginForm.password" type="password" show-password placeholder="密码" size="large">
                <template #prefix><el-icon><Lock/></el-icon></template>
              </el-input>
            </el-form-item>
            <el-button type="primary" size="large" style="width:100%" :loading="loading" @click="doLogin">登 录</el-button>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="注册" name="register">
          <el-form :model="regForm" :rules="regRules" ref="regRef">
            <el-form-item prop="username">
              <el-input v-model="regForm.username" placeholder="用户名（2-30个字符）" size="large">
                <template #prefix><el-icon><User/></el-icon></template>
              </el-input>
            </el-form-item>
            <el-form-item prop="nickname">
              <el-input v-model="regForm.nickname" placeholder="昵称（选填）" size="large">
                <template #prefix><el-icon><Postcard/></el-icon></template>
              </el-input>
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="regForm.password" type="password" show-password placeholder="密码（至少6位）" size="large">
                <template #prefix><el-icon><Lock/></el-icon></template>
              </el-input>
            </el-form-item>
            <el-form-item prop="confirm">
              <el-input v-model="regForm.confirm" type="password" show-password placeholder="确认密码" size="large">
                <template #prefix><el-icon><Lock/></el-icon></template>
              </el-input>
            </el-form-item>
            <el-button type="primary" size="large" style="width:100%" :loading="loading" @click="doRegister">注 册</el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
      <div class="login-tip">
        演示账号：用户 demo / 123456　管理员 admin / 123456<br>
        注册登录后即可上传简历，AI 自动生成优化建议与岗位适配分析
      </div>
    </div>
  </div>`,
  data() {
    return {
      tab: 'login',
      loading: false,
      loginForm: { username: '', password: '' },
      regForm: { username: '', nickname: '', password: '', confirm: '' },
      loginRules: {
        username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
        password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
      },
      regRules: {
        username: [{ required: true, min: 2, max: 30, message: '用户名长度 2-30 个字符', trigger: 'blur' }],
        password: [{ required: true, min: 6, message: '密码至少 6 位', trigger: 'blur' }],
        confirm: [{
          validator: (rule, value, cb) => {
            if (value !== this.regForm.password) cb(new Error('两次输入的密码不一致'));
            else cb();
          }, trigger: 'blur',
        }],
      },
    };
  },
  methods: {
    goHome(user) {
      this.$router.push(user.role === 'admin' ? '/admin/dashboard' : '/workbench');
    },
    doLogin() {
      this.$refs.loginRef.validate(async (ok) => {
        if (!ok) return;
        this.loading = true;
        try {
          const d = await api.post('/auth/login', this.loginForm);
          setStoredLogin(d.token, d.user);
          ElementPlus.ElMessage.success('登录成功');
          this.goHome(d.user);
        } catch (e) { ElementPlus.ElMessage.error(e.message); }
        this.loading = false;
      });
    },
    doRegister() {
      this.$refs.regRef.validate(async (ok) => {
        if (!ok) return;
        this.loading = true;
        try {
          const d = await api.post('/auth/register', this.regForm);
          setStoredLogin(d.token, d.user);
          ElementPlus.ElMessage.success('注册成功');
          this.goHome(d.user);
        } catch (e) { ElementPlus.ElMessage.error(e.message); }
        this.loading = false;
      });
    },
  },
};
