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
      server.middlewares.use('/results', (req, res, next) => {
        const reqPath = decodeURIComponent(req.url.split('?')[0].replace(/^\//, ''))
        const searchDirs = [
          path.resolve(__dirname, '../agents/registration_manager/results'),
          path.resolve(__dirname, '../agents/receipt_scanner/results'),
          path.resolve(__dirname, '../agents/video_editor/results'),
          path.resolve(__dirname, '../agents/video_editor/assets'),
        ]
        for (const dir of searchDirs) {
          const filePath = path.join(dir, reqPath)
          if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
            const ext = path.extname(filePath).toLowerCase()
            const mimeTypes = {
              '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
              '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
              '.csv': 'text/csv; charset=utf-8',
              '.pdf': 'application/pdf',
              '.mp4': 'video/mp4',
              '.png': 'image/png',
              '.jpg': 'image/jpeg',
              '.jpeg': 'image/jpeg',
              '.webp': 'image/webp',
            }
            res.setHeader('Content-Type', mimeTypes[ext] || 'application/octet-stream')
            res.setHeader('Content-Disposition', `attachment; filename="${path.basename(filePath)}"`)
            fs.createReadStream(filePath).pipe(res)
            return
          }
        }
        next()
      })
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
