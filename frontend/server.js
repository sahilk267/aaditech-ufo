import fs from 'fs'
import http from 'http'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const distDir = path.join(__dirname, 'dist')
const port = process.env.PORT || 3000

const contentTypes = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.map': 'application/octet-stream',
}

const getContentType = (filePath) => contentTypes[path.extname(filePath).toLowerCase()] || 'application/octet-stream'

const serveFile = (filePath, res) => {
  if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    return false
  }

  const stream = fs.createReadStream(filePath)
  res.writeHead(200, { 'Content-Type': getContentType(filePath) })
  stream.pipe(res)
  return true
}

const server = http.createServer((req, res) => {
  const requestedPath = new URL(req.url, `http://${req.headers.host}`).pathname

  if (requestedPath === '/app') {
    res.writeHead(301, { Location: '/app/' })
    res.end()
    return
  }

  if (!requestedPath.startsWith('/app/')) {
    res.writeHead(404)
    res.end('Not found')
    return
  }

  const appPath = requestedPath.slice('/app'.length) || '/'
  const normalized = path.posix.normalize(appPath)
  const filePath = normalized === '/'
    ? path.join(distDir, 'index.html')
    : path.join(distDir, normalized)

  if (serveFile(filePath, res)) {
    return
  }

  if (normalized === '/' || !path.extname(normalized)) {
    const indexPath = path.join(distDir, 'index.html')
    if (serveFile(indexPath, res)) {
      return
    }
  }

  res.writeHead(404)
  res.end('Not found')
})

server.listen(port, () => {
  console.log(`Frontend static server listening on port ${port}`)
})
