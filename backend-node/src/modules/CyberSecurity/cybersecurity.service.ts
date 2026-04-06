import { NextFunction, Request, Response } from "express";
import { FileRepository } from "../../DB/repositories/file.repository";
import fileModel from "../../DB/models/File.model";
import axios from "axios";
import { AppError } from "../../utils/ClassError";
import fs from "fs";
import path from "path"; // تأكدي إن السطر ده موجود فوق
import FormData from "form-data";

class CyberSecurityService {
  private _fileModel = new FileRepository(fileModel);
  private scanUrl: string;

  constructor() {
    // الأفضل نستخدم اسم الكونتينر مباشرة في الدوكر
    this.scanUrl = process.env.CYBER_SCAN_URL || "http://cyber-service:5000/scan";
  }

  scan = async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { fileId } = req.params;

      if (!fileId || Array.isArray(fileId)) {
        throw new AppError("Invalid fileId", 400);
      }

      const file = await this._fileModel.findById(fileId);
      if (!file) throw new AppError("File not found", 404);

      if (file.userId.toString() !== req.user?.id) {
        throw new AppError("You are not authorized to scan this file", 403);
      }

      // --- التعديل السحري هنا ---
      // 1. تحويل السلاش من \ لـ / عشان اللينكس يفهمها
      // 2. التأكد إن المسار بيبدأ من /app عشان يطابق الـ Volume في الدوكر
      const fixedPath = file.path.replace(/\\/g, '/');
      const absolutePath = path.resolve("/app", fixedPath);

      console.log("🕵️ Checking file at:", absolutePath);

      if (!fs.existsSync(absolutePath)) {
        throw new AppError(`File not found on server at: ${absolutePath}`, 404);
      }
      // --------------------------

      const formData = new FormData();
      formData.append("file", fs.createReadStream(absolutePath));

      const response = await axios.post(this.scanUrl, formData, {
        headers: {
          ...formData.getHeaders(),
        },
        timeout: 600000,
      });

      const data = response.data;

      const updatedFile = await this._fileModel.findOneAndUpdate(
        { _id: fileId },
        {
          $set: {
            security: {
              riskScore: data.security_score?.score || 0,
              riskLevel: data.step2_gate_report?.risk_level || 0,
              riskLabel: data.step2_gate_report?.risk_label || "Unknown",
              malwareRisk: data.security_score?.malware_risk || "Unknown",
              promptInjectionRisk: data.security_score?.prompt_injection_risk || "Unknown",
              contentModeration: data.security_score?.content_moderation || "Unknown",
            },
            scanTextSummary: data.summary || "",
            scanStatus: "completed",
          },
        },
        { new: true },
      );

      let safe = updatedFile?.security?.riskLevel !== 3;

      return res.json({
        message: "Scan completed successfully",
        fileIsSafe: safe,
        updatedFile,
      });
    } catch (error: any) {
      console.error("❌ Scan Error:", error.message);

      if (axios.isAxiosError(error)) {
        return next(new AppError(`Cyber Service Error: ${error.message}`, 503));
      }

      next(error);
    }
  };
}

export default new CyberSecurityService();