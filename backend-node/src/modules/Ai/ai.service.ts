import { NextFunction, Request, Response } from "express";
import { FileRepository } from "../../DB/repositories/file.repository";
import fileModel, { IFile } from "../../DB/models/File.model";
import fs from "fs";
import { AppError } from "../../utils/ClassError";
import axios from "axios";
import http from "http";
import https from "https";
import { summarizeSchema } from "./ai.validation";
import { ChatRepository } from "../../DB/repositories/chat.repository";
import chatModel, { Source } from "../../DB/models/chat.model";
import mongoose from "mongoose";
import path from "path";

function deduplicateSources(sources: Source[]): Source[] {
  const map = new Map<string, Source>();

  for (const item of sources) {
    const key = `${item.source}-${item.page}`;

    if (!map.has(key)) {
      map.set(key, item);
    }
  }

  return Array.from(map.values());
}

class AiService {
  constructor() {
    this.aiBaseUrl = process.env.AI_SERVICE_URL || "http://localhost:8000";
    this.aiBaseUrlCsv = process.env.AI_CSV_URL || "http://localhost:5001";
  }
  private _fileModel = new FileRepository(fileModel);
  private _chatModel = new ChatRepository(chatModel);
  private aiBaseUrl: string;
  private aiBaseUrlCsv: string;

  private transformSuggestions(aiData: any) {
    if (!aiData?.suggestions) return [];

    return aiData.suggestions.map((s: any) => ({
      id: s.id,
      title: s.title,
      description: s.description,
      chartType: s.type,

      mapping: {
        ...(s.x_col && {
          x: {
            column: s.x_col,
            type: this.inferType(s.x_col),
          },
        }),

        ...(s.y_col && {
          y: {
            column: s.y_col,
            type: this.inferType(s.y_col),
          },
        }),

        ...(s.color_col && {
          color: {
            column: s.color_col,
            type: this.inferType(s.color_col),
          },
        }),
      },

      options: {
        aggregation: s.agg,
      },
    }));
  }

  private inferType(column: string): "number" | "string" | "date" {
    const col = column.toLowerCase();

    if (col.includes("date") || col.includes("time")) return "date";

    if (
      col.includes("price") ||
      col.includes("amount") ||
      col.includes("revenue") ||
      col.includes("count")
    )
      return "number";

    return "string";
  }

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

      const filePath = path.resolve(file.path);

      if (!filePath || !fs.existsSync(filePath)) {
        throw new AppError("File not found on disk", 404);
      }

      if (file.summary) {
        return res.json({
          message: "Already summarized",
          summary: file.summary,
          fileUrl: `${req.protocol}://${req.get("host")}/${file.path}`,
          fileName: file.fileName.replace(/^\d+-/, ""),
        });
      }

      const response = await axios.post(
        `${this.aiBaseUrl}/api/summarize`,
        { filePath, fileId },
        {
          timeout: 600000,
          httpAgent: new http.Agent({ keepAlive: true }),
          httpsAgent: new https.Agent({ keepAlive: true }),
        },
      );

      if (response.data.status === "success" && response.data.summary) {
        const summary = response.data.summary;

        const updatedFile = await this._fileModel.findOneAndUpdate(
          { _id: fileId },
          { summary },
          { new: true },
        );

        return res.json({
          message: "Summary retrieved successfully",
          summary: updatedFile?.summary,
          fileUrl: `${req.protocol}://${req.get("host")}/${file.path}`,
          fileName: file.fileName.replace(/^\d+-/, ""),
        });
      }

      if (response.data.status === "processing") {
        const cacheKey = response.data.metadata?.cache_key || fileId;
        const maxPolls = 120;
        let pollCount = 0;

        while (pollCount < maxPolls) {
          await new Promise((resolve) => setTimeout(resolve, 5000));
          pollCount++;

          try {
            const pollResponse = await axios.post(
              `${this.aiBaseUrl}/api/summarize`,
              { filePath, fileId: cacheKey },
              { timeout: 30000 },
            );

            if (
              pollResponse.data.status === "success" &&
              pollResponse.data.summary
            ) {
              const summary = pollResponse.data.summary;

              const updatedFile = await this._fileModel.findOneAndUpdate(
                { _id: fileId },
                { summary },
                { new: true },
              );

              return res.json({
                message: "Summary retrieved successfully",
                summary: updatedFile?.summary,
                fileUrl: `${req.protocol}://${req.get("host")}/${file.path}`,
                fileName: file.fileName.replace(/^\d+-/, ""),
              });
            }
          } catch (pollError) {
            console.warn(
              `Poll attempt ${pollCount} failed:`,
              (pollError as Error).message,
            );
          }
        }

        throw new AppError("Summarization timed out", 504);
      }

      const summary = response.data.summary || "";
      const updatedFile = await this._fileModel.findOneAndUpdate(
        { _id: fileId },
        { summary },
        { new: true },
      );

      return res.json({
        message: "Summary retrieved successfully",
        summary: updatedFile?.summary,
        fileUrl: `${req.protocol}://${req.get("host")}/${file.path}`,
        fileName: file.fileName.replace(/^\d+-/, ""),
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

      const filePath = path.resolve(file.path);

      const response = await axios.post(
        `${this.aiBaseUrl}/api/ask`,
        {
          filePath,
          question,
          fileId,
        },
        {
          timeout: 600000,
          httpAgent: new http.Agent({ keepAlive: true }),
          httpsAgent: new https.Agent({ keepAlive: true }),
        },
      );

      // const answer: string = `lololollolo`;
      // let sources = [
      //   { source: "Networking Fundamentals lesson -5-.pdf", page: 1 },
      //   { source: "Networking Fundamentals lesson -5-.pdf", page: 3 },
      //   { source: "Networking Fundamentals lesson -5-.pdf", page: 4 },
      //   { source: "Networking Fundamentals lesson -5-.pdf", page: 4 },
      // ];
      const answer: string = response.data.answer;
      let sources: Source[] = response.data.sources;

      sources = deduplicateSources(sources);

      await this._chatModel.create({
        fileId: new mongoose.Types.ObjectId(fileId),
        question,
        answer,
        sources,
      });

      return res.json({
        message: "Answer retrieved successfully",
        answer,
        sources,
        fileName: file.fileName.replace(/^\d+-/, ""),
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
        fileName: file.fileName.replace(/^\d+-/, ""),
      });
    } catch (error: any) {
      if (error instanceof Error && "errors" in error) {
        return res.status(400).json({ message: (error as any).errors });
      }
      next(error);
    }
  };

  chartOptions = async (req: Request, res: Response, next: NextFunction) => {
    const { fileId } = req.params;
    const userId = req.user?._id?.toString();

    if (!userId) throw new AppError("Invalid userId", 401);
    if (!fileId) throw new AppError("Invalid fileId", 400);

    const file = await this._fileModel.findOne({ _id: fileId });
    if (!file) throw new AppError("File not found", 404);

    if (file.userId.toString() !== userId) {
      throw new AppError("Unauthorized", 403);
    }

    if (file.fileType !== "csv") {
      throw new AppError("Only CSV supported", 400);
    }

    if (!file.autoclean) {
      throw new AppError("File not ready for charts", 400);
    }

    const response = await axios.post(
      `${this.aiBaseUrlCsv}/suggest`,
      {
        file_id: fileId,
      },
      {
        timeout: 600000,
      },
    );

    const { suggestions, source } = response.data;

    // const suggestions = [
    //   { type: "bar", x: "category", y: "sales", title: "Sales by Category" },
    //   { type: "scatter", x: "lollll", y: "saraaaaa", title: "Sales by sss" },
    // ];

    if (!suggestions || !Array.isArray(suggestions)) {
      throw new AppError("Invalid AI response", 500);
    }

    const transformedCharts = suggestions.map((chart: any, index: number) => {
      const mapping: any = {};

      if (chart.x) {
        mapping.x = {
          column: chart.x,
          type: "string",
        };
      }

      if (chart.y) {
        mapping.y = {
          column: chart.y,
          type: "number",
        };
      }

      return {
        id: `chart_${index + 1}`,
        title: chart.title,
        chartType: chart.type,
        mapping,
      };
    });

    file.charts = transformedCharts;
    await file.save();

    return res.status(200).json({
      message: "Charts suggested successfully",
      charts: transformedCharts,
    });
  };

  visualizeCharts = async (req: Request, res: Response, next: NextFunction) => {
    const { fileId } = req.params;
    const { selectedCharts } = req.body;
    const userId = req.user?._id?.toString();

    if (!fileId) throw new AppError("Invalid fileId", 400);
    if (!selectedCharts || !Array.isArray(selectedCharts)) {
      throw new AppError("selectedCharts must be an array", 400);
    }

    const file = await this._fileModel.findOne({ _id: fileId });
    if (!file) throw new AppError("File not found", 404);

    if (file.userId.toString() !== userId) {
      throw new AppError("Unauthorized", 403);
    }

    if (file.fileType !== "csv") {
      throw new AppError("Only CSV supported", 400);
    }

    const chartsToSend = file.charts?.filter((chart) =>
      selectedCharts.includes(chart.id),
    );

    if (!chartsToSend || chartsToSend.length === 0) {
      throw new AppError("No valid charts selected", 400);
    }

    const response = await axios.post(
      `${this.aiBaseUrlCsv}/render`,
      {
        file_id: fileId,
        charts: chartsToSend.map((c) => ({
          type: c.chartType,
          x: c.mapping?.x?.column ?? null,
          y: c.mapping?.y?.column ?? null,
        })),
      },
      { timeout: 600000 },
    );

    const aiCharts = response.data.charts;

    // const aiCharts = [
    //   {
    //     success: true,
    //     title: "Sales by Category",
    //     fig: {
    //       data: [
    //         {
    //           type: "bar",
    //           x: ["Electronics", "Clothing", "Groceries", "Books"],
    //           y: [1200, 800, 1500, 400],
    //           marker: {
    //             color: "#636EFA",
    //           },
    //         },
    //       ],
    //       layout: {
    //         title: "Sales by Category",
    //         xaxis: {
    //           title: "Category",
    //         },
    //         yaxis: {
    //           title: "Sales",
    //         },
    //       },
    //     },
    //   },
    // ];

    if (!aiCharts || !Array.isArray(aiCharts)) {
      throw new AppError("Invalid AI response", 500);
    }

    const figMap = new Map(aiCharts.map((c: any) => [c.title, c]));

    file.charts = file.charts?.map((chart) => {
      const aiChart = figMap.get(chart.title);

      if (aiChart?.success) {
        return {
          ...chart,
          fig: aiChart.fig,
        };
      }

      return chart;
    });

    await file.save();

    const updatedSelectedCharts = file.charts
      ?.filter((chart) => selectedCharts.includes(chart.id))
      .map((chart) => ({
        id: chart.id,
        title: chart.title,
        chartType: chart.chartType,
        mapping: chart.mapping,
        fig: chart.fig,
      }));

    return res.status(200).json({
      message: "Charts rendered successfully",
      charts: updatedSelectedCharts,
    });
  };

  getCharts = async (req: Request, res: Response, next: NextFunction) => {
    const userId = req?.user?._id;
    const { fileId } = req.params;

    if (!fileId) throw new AppError("File not found", 404);

    if (!userId) throw new AppError("User Not found", 404);

    const file = await this._fileModel.findOne({
      _id: fileId,
      userId,
    });

    if (!file) throw new AppError("File Not Exist", 400);

    const charts = file.charts.map((chart) => ({
      id: chart.id,
      title: chart.title,
      hasFigure: !!chart.fig,
      fig: chart.fig || null,
      mapping: chart.mapping || null,
      chartType: chart.chartType,
    }));

    return res.status(200).json({ message: "success", charts });
  };
}

export default new AiService();