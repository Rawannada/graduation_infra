import { HydratedDocument, Model } from "mongoose";
import { IUser } from "../models/user.model";
import { DbRepository } from "./db.repository";
import { AppError } from "../../utils/ClassError";

export class UserRepository extends DbRepository<IUser> {

  constructor(protected readonly model: Model<IUser>) {
    super(model)
  }

  async createOneUser (data: Partial<IUser>): Promise<HydratedDocument<IUser>> {
    const user = this.model.create(data)

    if(!user)
      throw new AppError('Fail to create')

    return user
    
  }

}