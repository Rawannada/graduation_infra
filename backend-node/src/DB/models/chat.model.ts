import mongoose, { Schema, Types } from "mongoose";

export interface IChat {
  fileId: Types.ObjectId;
  question: string;
  answer: string;
  createdAt: Date;
}

const ChatSchema = new Schema<IChat>({
  fileId: { type: Schema.Types.ObjectId, ref: "File", required: true },
  question: { type: String, required: true },
  answer: { type: String, required: true },
  createdAt: { type: Date, default: Date.now },
});

const chatModel = mongoose.models.Chat || mongoose.model<IChat> ('Chat', ChatSchema)

export default chatModel