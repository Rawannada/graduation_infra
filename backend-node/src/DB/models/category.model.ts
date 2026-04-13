import mongoose, { Schema, Types } from "mongoose";

export interface ICategory {
  userId: Types.ObjectId;
  categoryName: string;
  createdAt: Date;
}

const categorySchema = new Schema<ICategory>({
  userId: { type: Schema.Types.ObjectId, ref: "User", required: true },
  categoryName: { type: String, required: true, trim: true },
  createdAt: { type: Date, default: Date.now },
});

const categoryModel = mongoose.models.Category || mongoose.model<ICategory>('Category', categorySchema)

export default categoryModel