import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { useNavigate } from "react-router-dom";

import line_img from "../src/assets/charts/line.svg";
import scatter_img from "../src/assets/charts/scatter.svg";
import heat_img from "../src/assets/newphotos/heat.svg";
import histo_img from "../src/assets/charts/histo.svg";
import bar_img from "../src/assets/newphotos/bar.svg";
import pie_img from "../src/assets/newphotos/pie.svg";

import { PanelLeft, Check } from "lucide-react";
export default function CSVColumns() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const { fileId, accessToken, fileName } = state || {};
  const [generating, setGenerating] = useState(false);
  const [charts, setCharts] = useState([]);
  const [selectedCharts, setSelectedCharts] = useState([]);
  const [loading, setLoading] = useState(false);

  // ---------------- FETCH CHART OPTIONS ----------------
  useEffect(() => {
    if (fileId) {
      getChartOptions();
    }
  }, [fileId]);

  // If no fileId (e.g., page refresh lost navigation state), redirect back
  if (!fileId) {
    return (
      <div style={{ padding: "2rem", textAlign: "center" }}>
        <p>No file selected. Please go back and upload a CSV file first.</p>
        <button onClick={() => navigate("/")} style={{ padding: "8px 16px", cursor: "pointer" }}>
          Go Back
        </button>
      </div>
    );
  }
  const chartImages = {
    line: line_img,
    scatter: scatter_img,
    heatmap: heat_img,
    bar: bar_img,
    histogram: histo_img,
    pie: pie_img,
  };
  const chartTypeColors = {
    bar: "#849275",
    line: "#41B6A3",
    scatter: "#7441B6",
    histogram: "#A82F50",
    pie: "#4A5699",
    heatmap: "#DBA020",
  };

  async function getChartOptions() {
    setLoading(true);

    try {
      const res = await fetch(`/api/ai/chart/${fileId}`, {
        method: "PATCH",
        headers: {
          Authorization: `bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
      });

      const data = await res.json();
      console.log(data);
      if (res.ok) {
        setCharts(data.charts || []);
      }
    } catch (err) {
      console.error("Chart Options Error:", err);
    } finally {
      setLoading(false);
    }
  }

  // ---------------- TOGGLE CHECKBOX ----------------
  function toggleChart(id) {
    setSelectedCharts((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  // ---------------- GENERATE VISUALIZATION ----------------
  async function generateCharts() {
    setGenerating(true);

    try {
      const res = await fetch(`/api/ai/visualize/${fileId}`, {
        method: "POST",
        headers: {
          Authorization: `bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          selectedCharts,
        }),
      });

      const data = await res.json();

      if (res.ok) {
        navigate("/dashboard", {
          state: {
            charts: data.charts,
          },
        });
      }
    } catch (err) {
      console.error(err);
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div style={{}} className="columns">
      <div className="title">
        <PanelLeft size={20} />
        <span>Data Relationships Found ({charts.length})</span>{" "}
      </div>
      <div className="coldisc">
        {" "}
        <span>
          Select the charts you want to add to your synthesis dashboard
        </span>
        <span className="analyze">"{fileName}"analyzed successfully</span>
      </div>

      {/* LOADING */}
      {loading && (
        <>
          {[...Array(5)].map((_, i) => (
            <div key={i} className="skeleton-option">
              {/* LEFT */}
              <div className="skeleton-left">
                <div className="skeleton-img skeleton-shimmer" />

                <div className="skeleton-texts">
                  <div className="skeleton-title skeleton-shimmer" />
                  <div className="skeleton-mapping skeleton-shimmer" />
                </div>
              </div>

              {/* RIGHT */}
              <div className="skeleton-right">
                <div className="skeleton-label skeleton-shimmer" />
                <div className="skeleton-checkbox skeleton-shimmer" />
              </div>
            </div>
          ))}
        </>
      )}

      {/* CHART LIST */}
      <div className="optionss">
        {!loading &&
          charts.map((chart) => (
            <div
              key={chart.id}
              style={{
                border: `2px solid ${chartTypeColors[chart.chartType?.toLowerCase()] || "#ddd"
                  }`,
              }}
              className="option"
            >
              <div className="option-content">
                <div className="chart-desc">
                  <div className="img">
                    <img
                      src={chartImages[chart.chartType?.toLowerCase()]}
                      alt={chart.chartType}
                    />
                    <span
                      className="chart-type"
                      style={{
                        color: chartTypeColors[chart.chartType] || "#333",
                        fontWeight: "600",
                        fontSize: "18px",
                      }}
                    >
                      {chart.chartType}
                    </span>
                  </div>
                  <div className="titlle">
                    {chart.title}

                    <span className="mapping">
                      mapping:
                      <span className="badgee">{chart.mapping?.x?.column}</span>
                      <span>&</span>
                      <span className="badgee">{chart.mapping?.y?.column}</span>
                    </span>
                  </div>
                </div>
                <div className="inputt">
                  <span>add to dashboard</span>
                  <div className="custom-check-wrapper">
                    <input
                      id={`chart-${chart.id}`}
                      type="checkbox"
                      checked={selectedCharts.includes(chart.id)}
                      onChange={() => toggleChart(chart.id)}
                    />
                    <Check className="check-icon" size={20} />
                  </div>
                </div>
              </div>
            </div>
          ))}
      </div>
      {/* BUTTON */}
      <div className="footerparent">
        <div className="footer">
          <span style={{ color: "#7F7F7F" }}>AI-powered chart suggestions</span>
          <div className="chartbtns">
            <button className="cancell">cancel</button>
            <button
              className="create"
              onClick={generateCharts}
              disabled={selectedCharts.length === 0 || generating}
            >
              {generating ? "Generating..." : "Create Dashboard"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
