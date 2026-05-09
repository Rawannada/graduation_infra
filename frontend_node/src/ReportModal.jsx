import { CircleX } from "lucide-react";

export default function ReportModal({ report, onClose }) {
  if (!report) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <div style={{ backgroundColor: "#EAEAEA" }} className="modal-header">
          <h3 style={{ color: "#113567" }}>Technical Analysis Report</h3>
          <button className="close-btn" onClick={onClose}>
            <CircleX />
          </button>
        </div>

        <div className="modal-body">
          <div className="report-grid">
            <div className="report-item">
              <span>file_id</span>
              <br />
              <div>{report?._id}</div>
            </div>
            <div className="report-item">
              <span>file_name</span>
              <br />
              <div>{report?.fileName}</div>
            </div>
            <div className="report-item">
              <span>file_path</span>
              <br />
              <div>{report?.path}</div>
            </div>
            <div className="report-item">
              <span>scan_status</span>
              <br />
              <div>{report?.scanStatus}</div>
            </div>
            <div className="report-item">
              <span>ScanTextSummary</span>
              <br />
              <div>{report?.scanTextSummary}</div>
            </div>
            <div className="report-item">
              <span>Risk_Score</span>
              <span
                style={{
                  color: report?.security?.riskScore > 70 ? "red" : "green",
                }}
              >
                <br />
                <div>{report?.security?.riskScore}%</div>
              </span>
            </div>
            <div className="report-item">
              <span>Malware_Analysis</span>
              <br />
              <div>{report?.security?.malwareRisk}</div>
            </div>
            <div className="report-item">
              <span>Prompt_Injection</span>
              <br />
              <div>{report?.security?.promptInjectionRisk}</div>
            </div>
            <div className="report-item">
              <span>Content_Moderation</span>
              <br />
              <div>{report?.security?.contentModeration}</div>
            </div>
            <div className="report-item">
              <span>Risk_Label</span>
              <br />
              <div>{report?.security?.riskLabel}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
