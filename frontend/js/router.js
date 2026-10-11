/* 路由定义（hash 模式，无需服务端回退） */
/* global VueRouter, UserLayout, AdminLayout, Login, Workbench, MyHistory, Profile,
   AdminDashboard, AdminUsers, AdminModels, AdminPrompts, AdminHistory */

const routes = [
  { path: '/login', component: Login },
  {
    path: '/',
    component: UserLayout,
    redirect: '/workbench',
    children: [
      { path: 'workbench', component: Workbench, meta: { auth: true } },
      { path: 'history', component: MyHistory, meta: { auth: true } },
      { path: 'profile', component: Profile, meta: { auth: true } },
    ],
  },
  {
    path: '/admin',
    component: AdminLayout,
    redirect: '/admin/dashboard',
    children: [
      { path: 'dashboard', component: AdminDashboard, meta: { auth: true, admin: true } },
      { path: 'users', component: AdminUsers, meta: { auth: true, admin: true } },
      { path: 'models', component: AdminModels, meta: { auth: true, admin: true } },
      { path: 'prompts', component: AdminPrompts, meta: { auth: true, admin: true } },
      { path: 'history', component: AdminHistory, meta: { auth: true, admin: true } },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
];

const router = VueRouter.createRouter({
  history: VueRouter.createWebHashHistory(),
  routes,
});

router.beforeEach((to) => {
  const token = localStorage.getItem('ro_token');
  const user = getStoredUser();
  if (to.meta.auth && !token) return '/login';
  if (to.meta.admin && (!user || user.role !== 'admin')) return '/';
  if (to.path === '/login' && token) return user && user.role === 'admin' ? '/admin/dashboard' : '/workbench';
  return true;
});
