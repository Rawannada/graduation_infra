import mongoose, { Schema, model, Types } from "mongoose";

export interface IFile {
  userId: Types.ObjectId;
  fileName: string;
  path: string;

  security?: {
    riskScore: number;
    riskLevel: number;
    riskLabel: string;
    malwareRisk: string;
    promptInjectionRisk: string;
    contentModeration: string;
  };

  // scanStatus?: "pending" | "completed" | "failed";

  scanTextSummary?: string;

  summary?: string;

  createdAt: Date;
  updatedAt: Date;
}

const fileSchema = new Schema<IFile>(
  {
    userId: {
      type: Schema.Types.ObjectId,
      ref: "User",
      required: true,
    },

    fileName: {
      type: String,
      required: true,
    },

    path: {
      type: String,
      required: true,
    },

    security: {
      riskScore: Number,
      riskLevel: Number,
      riskLabel: String,
      malwareRisk: String,
      promptInjectionRisk: String,
      contentModeration: String,
    },

    // scanStatus: {
    //   type: String,
    //   enum: ["pending", "completed", "failed"],
    //   default: "pending",
    // },

    scanTextSummary: String, 

    summary: String,
  },
  {
    timestamps: true,
  }
);

const fileModel =
  mongoose.models.File || mongoose.model<IFile>("File", fileSchema);

export default fileModel;