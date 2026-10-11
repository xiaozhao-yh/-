/* 个人中心：头像、资料、修改密码 */
/* global Vue, api, API_BASE, getStoredUser, setStoredLogin, ElementPlus */

const Profile = {
  template: `
  <div class="profile-cards">
    <div class="page-card">
      <h3 style="margin-top:0">头像</h3>
      <div class="avatar-box">
        <el-avatar :size="110" :src="avatarUrl" v-if="user && user.avatar"></el-avatar>
        <el-avatar :size="110" v-else><el-icon :size="48"><UserFilled/></el-icon></el-avatar>
        <div style="margin-top:14px">
          <el-upload :show-file-list="false" :http-request="uploadAvatar" accept=".png,.jpg,.jpeg,.gif,.webp">
            <el-button type="primary" plain><el-icon><Upload/></el-icon>上传头像</el-button>
          </el-upload>
        </div>
        <div class="tip">支持 png / jpg / gif / webp，5MB 以内</div>
      </div>
    </div>

    <div style="display:flex;flex-direction:column;gap:14px">
      <div class="page-card">
        <h3 style="margin-top:0">基本信息</h3>
        <el-form :model="infoForm" label-width="80px" style="max-width:460px">
          <el-form-item label="用户名"><el-input v-model="infoForm.username" disabled/></el-form-item>
          <el-form-item label="角色"><el-tag :type="user && user.role === 'admin' ? 'danger' : 'info'">{{ user && user.role === 'admin' ? '管理员' : '普通用户' }}</el-tag></el-form-item>
          <el-form-item label="昵称"><el-input v-model="infoForm.nickname" maxlength="30"/></el-form-item>
          <el-form-item label="邮箱"><el-input v-model="infoForm.email"/></el-form-item>
          <el-form-item label="手机号"><el-input v-model="infoForm.phone"/></el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="savingInfo" @click="saveInfo">保存修改</el-button>
          </el-form-item>
        </el-form>
      </div>
      <div class="page-card">
        <h3 style="margin-top:0">修改密码</h3>
        <el-form :model="pwdForm" label-width="80px" style="max-width:460px">
          <el-form-item label="原密码">
            <el-input v-model="pwdForm.old_password" type="password" show-password/>
          </el-form-item>
          <el-form-item label="新密码">
            <el-input v-model="pwdForm.new_password" type="password" show-password placeholder="至少6位"/>
          </el-form-item>
          <el-form-item label="确认密码">
            <el-input v-model="pwdForm.confirm" type="password" show-password/>
          </el-form-item>
          <el-form-item>
            <el-button type="warning" :loading="savingPwd" @click="savePwd">修改密码</el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </div>`,
  data() {
    return {
      user: getStoredUser(),
      infoForm: { username: '', nickname: '', email: '', phone: '' },
      pwdForm: { old_password: '', new_password: '', confirm: '' },
      savingInfo: false, savingPwd: false,
    };
  },
  computed: {
    avatarUrl() { return this.user && this.user.avatar ? API_BASE + this.user.avatar : ''; },
  },
  mounted() { this.infoForm = { username: this.user.username, nickname: this.user.nickname, email: this.user.email, phone: this.user.phone }; },
  methods: {
    async uploadAvatar(opts) {
      try {
        const fd = new FormData();
        fd.append('file', opts.file);
        const d = await api.post('/auth/avatar', fd);
        this.user = Object.assign({}, this.user, { avatar: d.avatar });
        setStoredLogin(localStorage.getItem('ro_token'), this.user);
        ElementPlus.ElMessage.success('头像已更新');
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
    },
    async saveInfo() {
      this.savingInfo = true;
      try {
        const d = await api.put('/auth/profile', { nickname: this.infoForm.nickname, email: this.infoForm.email, phone: this.infoForm.phone });
        this.user = d;
        setStoredLogin(localStorage.getItem('ro_token'), d);
        ElementPlus.ElMessage.success('基本信息已更新');
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
      this.savingInfo = false;
    },
    async savePwd() {
      if (!this.pwdForm.old_password || !this.pwdForm.new_password) { ElementPlus.ElMessage.warning('请填写完整'); return; }
      if (this.pwdForm.new_password.length < 6) { ElementPlus.ElMessage.warning('新密码至少 6 位'); return; }
      if (this.pwdForm.new_password !== this.pwdForm.confirm) { ElementPlus.ElMessage.warning('两次输入的新密码不一致'); return; }
      this.savingPwd = true;
      try {
        await api.put('/auth/password', { old_password: this.pwdForm.old_password, new_password: this.pwdForm.new_password });
        ElementPlus.ElMessage.success('密码修改成功');
        this.pwdForm = { old_password: '', new_password: '', confirm: '' };
      } catch (e) { ElementPlus.ElMessage.error(e.message); }
      this.savingPwd = false;
    },
  },
};
