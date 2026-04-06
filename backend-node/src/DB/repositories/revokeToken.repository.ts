import { Model } from "mongoose";
import { DbRepository } from "./db.repository";
import { IRevokeToken } from "../models/RevokeToken.model";

export class RevokeTokenRepository extends DbRepository<IRevokeToken>{
  constructor(protected model: Model<IRevokeToken>){
    super(model)
  }
}