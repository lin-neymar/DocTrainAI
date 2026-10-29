/**
 * 纯环境声明（不要写 import/export，否则会变成 module，IDE 可能吃不到）。
 * 让 .ts 里 import/动态 import `*.vue` 时能解析类型。
 */
declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}
