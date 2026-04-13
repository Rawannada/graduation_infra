import { Model } from "mongoose";
import { DbRepository } from "./db.repository";
import { ICategory } from "../models/category.model";

export class CategoryRepository extends DbRepository<ICategory> {
  constructor(protected model: Model<ICategory>) {
    super(model)
  }
}