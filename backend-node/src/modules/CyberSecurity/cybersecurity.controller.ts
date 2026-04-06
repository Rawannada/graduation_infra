import { Router } from "express";
import CS from './cybersecurity.service'
import { Authentication } from "../../middleware/Authentication";


const cyberSecurityRouter = Router()
cyberSecurityRouter.post('/scan/:fileId',Authentication(), CS.scan)


export default cyberSecurityRouter