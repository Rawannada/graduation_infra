import { Model } from "mongoose";
import { DbRepository } from "./db.repository";
import { IChat } from "../models/chat.model";

export class ChatRepository extends DbRepository<IChat>{
  constructor(protected model: Model<IChat>){
    super(model)
  }
}