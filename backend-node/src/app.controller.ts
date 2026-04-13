import express, { NextFunction, Request, Response } from 'express'
import cors from 'cors'
import helmet from 'helmet'
import { rateLimit } from 'express-rate-limit'
import { AppError } from './utils/ClassError'
import userRouter from './modules/users/user.controller'
import connectionDB from './DB/connectionDB'
import uploadRouter from './modules/UploadFile/upload.controller'
import aiRouter from './modules/Ai/ai.controller'
import cyberSecurityRouter from './modules/CyberSecurity/cybersecurity.controller'
const app: express.Application = express()
const port: string | number = process.env.PORT || 3000

const whitelist: (string | undefined)[] = [process.env.FRONT_END, undefined]
const corsOptions = {
  origin: (origin: string | undefined, callback: Function) => {
    if (whitelist.includes(origin)) {
      return callback(null, true);
    }
    return callback(new Error("Not Allowed by CORS"));
  }
};

const limiter = rateLimit({
  windowMs: 5 * 60 * 1000,
  statusCode: 429,
  limit: 100,
  message: {
    error: 'Many Requests, Try Again Later'
  },
  legacyHeaders: false,
  skipSuccessfulRequests: true
})


const bootstrap = async () => {
  app.use('/uploads', express.static("uploads"))
  app.use(express.json())
  app.use(cors(corsOptions))
  app.use(helmet())
  app.use(limiter)

  app.get('/', (req: Request, res: Response, next: NextFunction) => {
    return res.status(200).json({ message: 'Welcom To Our App 😁' })

  })

  app.use('/users', userRouter)
  app.use('/upload', uploadRouter)
  app.use('/ai', aiRouter)
  app.use('/security', cyberSecurityRouter)
  await connectionDB()

  app.use('{/*demo}', (req: Request, res: Response, next: NextFunction) => {
    throw new AppError(`InValid Url ${req.originalUrl}`, 404)
  })

  app.use((err: AppError, req: Request, res: Response, next: NextFunction) => {
    return res.status(err.cause as unknown as number || 500).json({ message: err.message, stack: err.stack })

  })




  const server = app.listen(port, () => {
    console.log(`Server is running on port: ${port}`);

  })

  server.timeout = 600000;
  server.keepAliveTimeout = 600000;
  server.headersTimeout = 601000;

}

export default bootstrap