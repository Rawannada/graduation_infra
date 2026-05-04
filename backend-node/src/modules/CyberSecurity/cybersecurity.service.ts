import { NextFunction, Request, Response } from "express";
import { FileRepository } from "../../DB/repositories/file.repository";
import fileModel from "../../DB/models/File.model";
import axios from "axios";
import { AppError } from "../../utils/ClassError";
import fs from "fs";
import FormData from "form-data";

class CyberSecurityService {
  private _fileModel = new FileRepository(fileModel);
  private scanUrl: string;

  constructor() {
    this.scanUrl =
      process.env.CYBER_SCAN_URL || "http://192.168.1.22:5000/scan";
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

      if (!fs.existsSync(file.path))
        throw new AppError("File not found on server", 404);

      const formData = new FormData();
      formData.append("file", fs.createReadStream(file.path));

      const response = await axios.post(this.scanUrl, formData, {
        headers: {
          ...formData.getHeaders(),
        },
        timeout: 600000,
      });

      const data = response.data;
      // const data = {
      //   file_path: "test_suite\\t6_phishing.pdf",
      //   file_type: "PDF",
      //   processed_at: "2026-04-13T19:26:29.113454+00:00",
      //   step1_ok: true,
      //   step1_reason: "File type validation passed.",
      //   step2_ok: true,
      //   step2_reason: "",
      //   step2_gate_report: {
      //     file_id: null,
      //     file_name: "test_suite\\t6_phishing.pdf",
      //     file_hash:
      //       "b64b5e685da3e89f1092777b3737580750b05801613934c9051bab249641d10d",
      //     created_at: "2026-04-13T19:26:29.200613+00:00",
      //     javascript_found: false,
      //     embedded_files: 0,
      //     suspicious_objects: 22,
      //     triggers: [
      //       {
      //         type: "SinglePageDocument",
      //         page: 0,
      //       },
      //       {
      //         type: "/AA",
      //         page: 0,
      //       },
      //       {
      //         type: "/URI",
      //         page: 0,
      //       },
      //       {
      //         type: "/URI",
      //         page: 0,
      //       },
      //       {
      //         type: "/URI",
      //         page: 0,
      //       },
      //       {
      //         type: "/URI",
      //         page: 0,
      //       },
      //       {
      //         type: "/URI",
      //         page: 0,
      //       },
      //       {
      //         type: "/URI",
      //         page: 0,
      //       },
      //       {
      //         type: "/URI",
      //         page: 0,
      //       },
      //       {
      //         type: "/URI",
      //         page: 0,
      //       },
      //       {
      //         type: "/URI",
      //         page: 0,
      //       },
      //       {
      //         type: "/URI",
      //         page: 0,
      //       },
      //       {
      //         type: "/URI",
      //         page: 0,
      //       },
      //       {
      //         type: "/URI",
      //         page: 0,
      //       },
      //       {
      //         type: "/URI",
      //         page: 0,
      //       },
      //       {
      //         type: "/URI",
      //         page: 0,
      //       },
      //       {
      //         type: "/URI",
      //         page: 0,
      //       },
      //       {
      //         type: "/URI",
      //         page: 0,
      //       },
      //       {
      //         type: "/AA",
      //         location: "Root/Document-level",
      //       },
      //       {
      //         type: "/SubmitForm",
      //         location: "Root/Document-level",
      //       },
      //       {
      //         type: "/AcroForm",
      //         location: "Root/Document-level",
      //       },
      //       {
      //         type: "ManyExternalLinks",
      //         count: 16,
      //       },
      //     ],
      //     metadata: {},
      //     num_pages: 1,
      //     encrypted: false,
      //     objstm_count: 0,
      //     risk_level: 2,
      //     risk_label: "Medium",
      //     profile: "phishing_like",
      //     engine_version: "pdf-cyber-scanner-v3",
      //     security_block: false,
      //     security_decision: "review",
      //     trigger_stats: {
      //       SinglePageDocument: 1,
      //       "/AA": 2,
      //       "/URI": 16,
      //       "/SubmitForm": 1,
      //       "/AcroForm": 1,
      //       ManyExternalLinks: 1,
      //     },
      //     total_triggers: 22,
      //     flags: {
      //       has_javascript: false,
      //       has_embedded_files: false,
      //       has_forms: true,
      //       has_external_links: true,
      //       is_single_page: true,
      //       has_objstm: false,
      //       has_open_action: false,
      //       has_launch_action: false,
      //     },
      //     explanation: "High number of external links.",
      //   },
      //   step3_text: "URGENT: Verify your PayPal account immediately!\n",
      //   step3_error: null,
      //   step4_actions: [],
      //   step5_injection_detected: false,
      //   step5_matches: [],
      //   step6_dlp_findings: {},
      //   step6_total_redacted: 0,
      //   step7_threat_alert: false,
      //   step7_indicators: [],
      //   step7_urls_found: [],
      //   step8_content_blocked: false,
      //   step8_reason: "",
      //   step9_adversarial_detected: false,
      //   step9_techniques: [],
      //   security_score: {
      //     score: 82,
      //     malware_risk: "High",
      //     prompt_injection_risk: "None",
      //     sensitive_data: "None",
      //     threat_indicators: "None",
      //     adversarial_input: "None",
      //     content_moderation: "Passed",
      //     penalties: {
      //       many_links: 10,
      //       medium_risk_pdf: 8,
      //     },
      //   },
      //   status: "PROCESSING_COMPLETE",
      //   rejection_reason: "",
      //   clean_text: "URGENT: Verify your PayPal account immediately!\n",
      //   output_filter_removals: [],
      //   summary:
      //     "[Extractive Preview] URGENT: Verify your PayPal account immediately!",
      //   summary_confidence: 60,
      // };

      const updatedFile = await this._fileModel.findOneAndUpdate(
        { _id: fileId },
        {
          $set: {
            security: {
              riskScore: data.security_score.score,
              riskLevel: data.step2_gate_report.risk_level,
              riskLabel: data.step2_gate_report.risk_label,
              malwareRisk: data.security_score?.malware_risk || "Unknown",
              promptInjectionRisk:
                data.security_score?.prompt_injection_risk || "Unknown",
              contentModeration:
                data.security_score?.content_moderation || "Unknown",
              scanStatus: data.status,
              triggerStatus: data.step2_gate_report.trigger_stats || {},
            },
            scanTextSummary: data.summary || "",
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
      console.error(error);

      if (axios.isAxiosError(error)) {
        return next(new AppError(error.message, 503));
      }

      next(error);
    }
  };
}

export default new CyberSecurityService();
