import { Router } from "express";
import AS from './ai.service'
import { Authentication } from "../../middleware/Authentication";


const aiRouter = Router()

aiRouter.post('/summarize/:fileId', Authentication(), AS.summarize)
aiRouter.post('/ask/:fileId', Authentication(), AS.askQuestion)
aiRouter.get('/chat/:fileId', Authentication(), AS.getChatHistory)


export default aiRouter