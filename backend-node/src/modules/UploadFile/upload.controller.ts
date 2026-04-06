import { Router } from "express";
import { Authentication } from "../../middleware/Authentication";
import { allowedExtensions, MulterLocal } from "../../middleware/Multer";
import { validation } from "../../middleware/validation";
import * as UPV from "./upload.validation";
import UPS from './upload.service' 

const uploadRouter = Router()

uploadRouter.post('/', Authentication(), MulterLocal({customExtensions: allowedExtensions.pdf}).single('file'), UPS.upload)

export default uploadRouter