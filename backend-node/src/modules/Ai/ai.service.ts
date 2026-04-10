import { NextFunction, Request, Response } from "express";
import { FileRepository } from "../../DB/repositories/file.repository";
import fileModel from "../../DB/models/File.model";
import fs from "fs";
import { AppError } from "../../utils/ClassError";
import axios, { options } from "axios";
import http from "http";
import https from "https";
import { summarizeSchema } from "./ai.validation";
import { ChatRepository } from "../../DB/repositories/chat.repository";
import chatModel from "../../DB/models/chat.model";
import mongoose from "mongoose";
import FormData from "form-data";

class AiService {
  constructor() {
    this.aiBaseUrl = process.env.AI_SERVICE_URL || "http://host.docker.internal:8000";
  }
  private _fileModel = new FileRepository(fileModel);
  private _chatModel = new ChatRepository(chatModel);
  private aiBaseUrl: string;

  summarize = async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { fileId } = summarizeSchema.params.parse(req.params);

      if (!fileId || Array.isArray(fileId)) {
        throw new AppError("Invalid fileId", 400);
      }

      const file = await this._fileModel.findById(fileId);

      if (!file) {
        throw new AppError("File not found", 404);
      }

      if (file.userId.toString() !== req.user?.id) {
        throw new AppError(
          "You are not authorized to summarize this file",
          403,
        );
      }

      const filePath = file.path;
      console.log(filePath);

      if (!filePath || !fs.existsSync(filePath)) {
        throw new AppError("File not found on disk", 404);
      }

      if (file.summary) {
        return res.json({
          message: "Already summarized",
          summary: file.summary,
        });
      }

      const response = await axios.post(
        `${this.aiBaseUrl}/api/summarize`,
        { filePath },
        {
          timeout: 600000,
          httpAgent: new http.Agent({ keepAlive: true }),
          httpsAgent: new https.Agent({ keepAlive: true }),
        },
      );

      const summary = response.data.summary;

      const updatedFile = await this._fileModel.findOneAndUpdate(
        { _id: fileId },
        { summary },
        { new: true },
      );

      return res.json({
        message: "Summary retrieved successfully",
        summarize: updatedFile?.summary,
        fileUrl: `${req.protocol}://${req.get("host")}/${file.path}`,
      });
    } catch (error) {
      next(error);
    }
  };

  askQuestion = async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { fileId } = req.params;
      const { question } = req.body;

      if (!fileId || Array.isArray(fileId)) {
        throw new AppError("Invalid fileId", 400);
      }

      const file = await this._fileModel.findById(fileId);
      if (!file) throw new AppError("File not found", 404);

      if (file.userId.toString() !== req.user?.id) {
        throw new AppError(
          "You are not authorized to ask questions on this file",
          403,
        );
      }

      const response = await axios.post(
        `${this.aiBaseUrl}/api/ask`,
        {
          fileId,
          question,
        },
        {
          timeout: 600000,
          httpAgent: new http.Agent({ keepAlive: true }),
          httpsAgent: new https.Agent({ keepAlive: true }),
        },
      );

      // const answer: string = `response.data.answer`;
      const answer: string = response.data.answer;

      await this._chatModel.create({
        fileId: new mongoose.Types.ObjectId(fileId),
        question,
        answer,
        createdAt: new Date(),
      });

      return res.json({
        message: "Answer retrieved successfully",
        answer,
      });
    } catch (error: any) {
      if (error instanceof Error && "errors" in error) {
        return res.status(400).json({ message: (error as any).errors });
      }
      next(error);
    }
  };

  getChatHistory = async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { fileId } = req.params;

      if (!fileId || Array.isArray(fileId)) {
        throw new AppError("Invalid fileId", 400);
      }
      const file = await this._fileModel.findById(fileId);

      if (!file) throw new AppError("File not found", 404);

      if (file.userId.toString() !== req.user?.id) {
        throw new AppError("You are not authorized to view this chat", 403);
      }

      const chats = await this._chatModel.find({
        filter: { fileId: new mongoose.Types.ObjectId(fileId) },
        options: { sort: { createdAt: 1 } },
      });

      return res.json({
        message: "Chat history retrieved successfully",
        chats,
      });
    } catch (error: any) {
      if (error instanceof Error && "errors" in error) {
        return res.status(400).json({ message: (error as any).errors });
      }
      next(error);
    }
  };
}

export default new AiService();