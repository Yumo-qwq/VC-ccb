# 中文 VOCALOID 猜曲

纯前端 Vue 3 + Vite 猜曲网页。题库位于 `src/data/vcpedia_legendary_songs.json`，构建后会被打包进静态资源，不需要后端服务。

## 本地运行

```bash
npm install
npm run dev
```

## 构建部署

```bash
npm run build
```

将 `dist` 目录部署到 GitHub Pages、Netlify、Cloudflare Pages、Vercel 或任意静态站点服务即可。题库 1000 条以内直接放 JSON 通常没有问题；如果后续题库变大，可以把 JSON 放到 `public/` 并按需请求。

## 题库格式

```json
{
  "id": "song-id",
  "title": "曲名",
  "aliases": ["别名"],
  "year": 2018,
  "engine": "VOCALOID",
  "plays": 22000000,
  "producer": "P主",
  "singers": ["洛天依"]
}
```

数据信息来源于 vcpedia.cn，截止至 2026年8月6日。