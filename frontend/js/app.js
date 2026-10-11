/* 应用入口 */
/* global Vue, ElementPlus, ElementPlusIconsVue, router, renderMd */

const app = Vue.createApp({ template: '<router-view />' });
app.use(router);
app.use(ElementPlus, { locale: ElementPlusLocaleZhCn });
for (const [name, comp] of Object.entries(ElementPlusIconsVue)) {
  app.component(name, comp);
}
app.config.globalProperties.$md = renderMd;
app.mount('#app');
