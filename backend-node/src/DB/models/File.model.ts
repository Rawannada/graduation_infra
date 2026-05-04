import mongoose, { Schema, model, Types } from "mongoose";
import { chartSchema } from "./chart.schema";

export interface IFile {
  userId: Types.ObjectId;
  categoryId: Types.ObjectId;
  fileName: string;
  path: string;
  fileType: "pdf" | "csv" | "image";

  security?: {
    riskScore: number;
    riskLevel: number;
    riskLabel: string;
    malwareRisk: string;
    promptInjectionRisk: string;
    contentModeration: string;
    scanStatus: string;
    triggerStatus: Record<string, number>;
  };

  scanTextSummary?: string;
  summary?: string;

  autoclean?: {
    status?: "success" | "failed";
    raw_shape?: number[];
    clean_shape?: number[];
    rows_removed?: number;
    cleaned_path?: string;
    ready_for_charts?: boolean;
  };

  charts: {
    id: string;
    title: string;
    description?: string;

    fig?: any;

    chartType: string;

    mapping?: {
      x?: { column: string; type: "number" | "string" | "date" };
      y?: { column: string; type: "number" | "string" | "date" };
      value?: { column: string; type: "number" | "string" | "date" };
      category?: { column: string; type: "number" | "string" | "date" };
      color?: { column: string; type: "number" | "string" | "date" };
    };

    options?: {
      aggregation?: string;
    };
  }[];

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

    categoryId: {
      type: Schema.Types.ObjectId,
      ref: "Category",
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

    fileType: {
      type: String,
      enum: ["pdf", "csv", "image"],
      required: true,
    },

    security: {
      riskScore: Number,
      riskLevel: Number,
      riskLabel: String,
      malwareRisk: String,
      promptInjectionRisk: String,
      contentModeration: String,
      scanStatus: String,
      triggerStatus: {
        type: Map,
        of: Number,
        default: {},
      },
    },

    scanTextSummary: String,
    summary: String,

    autoclean: {
      status: {
        type: String,
        enum: ["success", "failed"],
      },
      raw_shape: {
        type: [Number],
      },
      clean_shape: {
        type: [Number],
      },
      rows_removed: Number,
      cleaned_path: String,
      ready_for_charts: Boolean,
    },

    charts: {
      type: [chartSchema],
      default: [],
    },
  },
  {
    timestamps: true,
  },
);

const fileModel =
  mongoose.models.File || mongoose.model<IFile>("File", fileSchema);

export default fileModel;
