import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

function serveAgentResultsPlugin() {
  return {
    name: 'serve-agent-results',
    configureServer(server) {
      const handleFileServe = (req, res, next) => {
        const cleanUrl = decodeURIComponent(req.url.split('?')[0].replace(/^\/(?:renders|results)\/?/, ''))
        if (!cleanUrl) return next()

        const searchDirs = [
          path.resolve(__dirname, '../agents/video_editor/renders'),
          path.resolve(__dirname, '../agents/registration_manager/results'),
          path.resolve(__dirname, '../agents/receipt_scanner/results'),
          path.resolve(__dirname, '../agents/video_editor/results'),
          path.resolve(__dirname, '../agents/video_editor/assets'),
        ]

        let targetFile = null
        for (const dir of searchDirs) {
          const cand = path.join(dir, cleanUrl)
          if (fs.existsSync(cand) && fs.statSync(cand).isFile()) {
            targetFile = cand
            break
          }
        }

        // Search recursively inside workspaces if not found in root folders
        if (!targetFile) {
          const workspacesDir = path.resolve(__dirname, '../agents/video_editor/workspaces')
          if (fs.existsSync(workspacesDir)) {
            const findRecursive = (dir) => {
              try {
                for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
                  const full = path.join(dir, entry.name)
                  if (entry.isDirectory()) {
                    findRecursive(full)
                    if (targetFile) return
                  } else if (entry.name === cleanUrl || entry.name === path.basename(cleanUrl)) {
                    targetFile = full
                    return
                  }
                }
              } catch (_) {}
            }
            findRecursive(workspacesDir)
          }
        }

        if (targetFile && fs.existsSync(targetFile)) {
          const stat = fs.statSync(targetFile)
          const ext = path.extname(targetFile).toLowerCase()
          const mimeTypes = {
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.csv': 'text/csv; charset=utf-8',
            '.pdf': 'application/pdf',
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',
            '.mov': 'video/quicktime',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.webp': 'image/webp',
            '.gif': 'image/gif',
          }
          const contentType = mimeTypes[ext] || 'application/octet-stream'

          res.setHeader('Access-Control-Allow-Origin', '*')
          res.setHeader('Accept-Ranges', 'bytes')

          const range = req.headers.range
          if (range) {
            const parts = range.replace(/bytes=/, '').split('-')
            const start = parseInt(parts[0], 10)
            const end = parts[1] ? parseInt(parts[1], 10) : stat.size - 1
            const chunksize = end - start + 1
            const stream = fs.createReadStream(targetFile, { start, end })

            res.writeHead(206, {
              'Content-Range': `bytes ${start}-${end}/${stat.size}`,
              'Accept-Ranges': 'bytes',
              'Content-Length': chunksize,
              'Content-Type': contentType,
            })
            stream.pipe(res)
            return
          }

          res.writeHead(200, {
            'Content-Length': stat.size,
            'Content-Type': contentType,
          })
          fs.createReadStream(targetFile).pipe(res)
          return
        }

        next()
      }

      server.middlewares.use('/results', handleFileServe)
      server.middlewares.use('/renders', handleFileServe)
    }
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [svelte(), serveAgentResultsPlugin()],
  server: {
    proxy: {
      '/list-apps': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
        headers: {
          Origin: 'http://127.0.0.1:8080'
        }
      },
      '/run': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
        headers: {
          Origin: 'http://127.0.0.1:8080'
        }
      },
      '/run_sse': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
        headers: {
          Origin: 'http://127.0.0.1:8080'
        }
      },
      '/apps': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
        headers: {
          Origin: 'http://127.0.0.1:8080'
        }
      }
    }
  }
})
