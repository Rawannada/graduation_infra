import { NextFunction, Request, Response } from "express"
import { AppError } from "../../utils/ClassError"
import { FileRepository } from "../../DB/repositories/file.repository"
import fileModel from "../../DB/models/File.model"

class UploadService {
  private _fileModel = new FileRepository(fileModel)

  upload = async(req: Request, res: Response, next: NextFunction) =>{
    const file = (req as any).file as Express.Multer.File | undefined
    const userId = req?.user?._id

    if(!file || !file.path || !userId)
      throw new AppError('Upload failed, Missing the file or UserId', 404)

    const pdf = await this._fileModel.create({
      userId,
      fileName: req?.file?.filename!,
      path: req?.file?.path!
    })

    return res.status(200).json({message: 'File uploaded successfully', pdf})
  }


}


export default new UploadService()