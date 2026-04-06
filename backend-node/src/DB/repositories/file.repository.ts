import { Model } from "mongoose";
import { DbRepository } from "./db.repository";
import { IFile } from "../models/File.model";

export class FileRepository extends DbRepository<IFile>{
  constructor(protected model: Model<IFile>){
    super(model)
  }
}