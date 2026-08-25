# 摄影师预约项目讲解大纲

面向对象：只有基础 Python 经验、希望补足工程理解与全栈协作思维的学习者。

使用方式：
- 我们按目录逐节讲，不追求一次讲完
- 每一节优先回答三个问题：`这是什么`、`为什么要这样设计`、`代码在哪里`
- 你先建立“系统地图”，再慢慢进入细节

## 1. 先认识这个项目
- 1.1 这个项目是做什么的
- 1.2 它服务哪些角色
- 1.3 用户端、管理端、移动端分别负责什么
- 1.4 这个项目的核心业务主线是什么

## 2. 看懂项目结构
- 2.1 `frontend`、`admin-frontend`、`mobile-app`、`backend` 的分工
- 2.2 `docs`、`assets`、`uploads`、`migrations`、`tests` 分别是什么
- 2.3 “前端-后端-数据库-缓存-文件存储”整条链路

## 3. 项目怎么启动
- 3.1 本地开发环境需要什么
- 3.2 `README.md` 里的启动命令是什么意思
- 3.3 `docker-compose.yml` 做了什么
- 3.4 为什么有本地 SQLite，也有 Docker PostgreSQL

## 4. 前端入口与页面路由
- 4.1 Vue 项目从哪里启动
- 4.2 `main.js` 做了哪些初始化
- 4.3 路由是什么，为什么页面切换不刷新
- 4.4 `App.vue` 作为总布局在做什么
- 4.5 页面、组件、状态管理分别承担什么职责

## 5. 后端入口与接口路由
- 5.1 FastAPI 是怎么启动的
- 5.2 `main.py` 为什么像总装配中心
- 5.3 router、service、model、schema 的分层
- 5.4 为什么接口大多挂在 `/api/v1`

## 6. 登录与鉴权
- 6.1 登录请求从前端到后端的完整路径
- 6.2 为什么这里用 JWT
- 6.3 `Authorization: Bearer <token>` 是什么
- 6.4 `token_version` 为什么能让旧登录失效
- 6.5 为什么要区分“已登录”和“当前活跃用户”

## 7. 账号体系
- 7.1 用户名、邮箱、手机号是怎么识别的
- 7.2 为什么要做邮箱和手机号验证
- 7.3 注册、登录、改密码、绑定邮箱/手机的关系
- 7.4 普通用户、摄影师、管理员三种角色

## 8. 数据库与数据模型
- 8.1 SQLAlchemy 模型是什么
- 8.2 表和对象之间是什么关系
- 8.3 为什么要有 Alembic 迁移
- 8.4 版本演进时数据库怎么不丢数据

## 9. 核心业务链路
- 9.1 浏览摄影师和作品
- 9.2 查看套餐和企划
- 9.3 创建预约订单
- 9.4 摄影师接单、拒单、改期
- 9.5 支付、验收、评价

## 10. 消息与通知
- 10.1 站内消息是怎么来的
- 10.2 WebSocket 的作用
- 10.3 通知和未读数为什么要单独管理

## 11. 文件上传与资源访问
- 11.1 头像、背景图、作品图怎么上传
- 11.2 本地存储和 MinIO/S3 的差别
- 11.3 `/static` 是怎么暴露文件的

## 12. AI 功能是怎么接入的
- 12.1 这个项目里 AI 解决什么问题
- 12.2 为什么会有 intent classifier、orchestrator、tool service
- 12.3 AI 不是直接回答，而是先判断意图再调用工具
- 12.4 为什么要做资源检索、向量索引、缓存

## 13. 测试与质量保障
- 13.1 单元测试、接口测试、端到端测试的区别
- 13.2 为什么这个项目测试文件很多
- 13.3 哪些地方最值得先看测试

## 14. 部署与环境切换
- 14.1 本地开发环境和生产环境的差别
- 14.2 `.env` 里的配置是怎么控制行为的
- 14.3 为什么 Docker 里会有 Postgres、Redis、MinIO

## 15. 学习顺序建议
- 第一步：先看项目结构和启动流程
- 第二步：先理解登录与鉴权
- 第三步：再看一个完整业务链路，比如“浏览摄影师 -> 下单 -> 消息 -> 验收”
- 第四步：最后再看 AI、消息、文件上传这些增强功能

## 16. 我们后续的讲解节奏
- 每次只讲一个主题
- 每次只抓一条主线
- 每讲完一节，补一个小例子
- 如果你听懂了，我们再往下一层走

## 17. 推荐的第一批阅读文件
- [backend/app/main.py](../backend/app/main.py)
- [backend/app/core/config.py](../backend/app/core/config.py)
- [backend/app/api/v1/users.py](../backend/app/api/v1/users.py)
- [backend/app/api/deps.py](../backend/app/api/deps.py)
- [backend/app/core/security.py](../backend/app/core/security.py)
- [frontend/src/main.js](../frontend/src/main.js)
- [frontend/src/router/index.js](../frontend/src/router/index.js)
- [frontend/src/views/Login.vue](../frontend/src/views/Login.vue)

