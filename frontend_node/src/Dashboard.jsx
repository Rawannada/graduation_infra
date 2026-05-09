import React, { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { PanelLeft, Download, Check } from "lucide-react";
import Plot from "react-plotly.js";
import JSZip from "jszip";
import { saveAs } from "file-saver";
import Plotly from "plotly.js-dist";
import axios from "axios";
export default function Dashboard() {
  const { state } = useLocation();

  const chartsFromState = state?.charts || [];
  const fileId = state?.fileId;
  const accessToken = state?.accessToken;

  const [charts, setCharts] = useState(chartsFromState);
  const [selectedCharts, setSelectedCharts] = useState([]);
const [loading, setLoading] = useState(true);


  const chartTypeColors = {
    bar: "#849275",
    line: "#41B6A3",
    scatter: "#7441B6",
    histogram: "#A82F50",
    pie: "#4A5699",
    heatmap: "#DBA020",
  };
  useEffect(() => {
    if (!fileId) return;

    const fetchHistory = async () => {
      try {
        setLoading(true);

        const res = await axios.get(
          `/api/ai/figures/${fileId}`,
          {
            headers: {
              Authorization: `bearer ${accessToken}`,
            },
          },
        );
        console.log("history response:", res.data);
        const historyCharts = res.data.charts || [];

        setCharts((prev) => {
          const merged = [...historyCharts, ...prev];

          return Array.from(new Map(merged.map((c) => [c.id, c])).values());
        });
      } catch (err) {
        console.log(err);
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, [fileId]);
  // ✅ Select All / Unselect All
  const handleSelectAll = () => {
    if (selectedCharts.length === charts.length) {
      setSelectedCharts([]);
    } else {
      setSelectedCharts(charts.map((c) => c.id));
    }
  };

  // ✅ Toggle Chart
  const toggleChart = (id) => {
    if (selectedCharts.includes(id)) {
      setSelectedCharts(selectedCharts.filter((x) => x !== id));
    } else {
      setSelectedCharts([...selectedCharts, id]);
    }
  };

  // ✅ Download ZIP
  const handleDownloadZip = async () => {
    const zip = new JSZip();

    const selected = charts.filter((chart) =>
      selectedCharts.includes(chart.id),
    );

    for (let i = 0; i < selected.length; i++) {
      const chart = selected[i];

      if (!chart.fig) continue;

      const imgData = await Plotly.toImage(chart.fig, {
        format: "png",
        width: 1000,
        height: 700,
      });

      const response = await fetch(imgData);
      const blob = await response.blob();

      zip.file(`${chart.title || "chart"}-${i}.png`, blob);
    }

    const content = await zip.generateAsync({ type: "blob" });
    saveAs(content, "charts.zip");
  };

  return (
    <div className="charts">
      {/* Header */}
      <div className="title">
        <PanelLeft size={20} />
        <span>Interactive Synthesis Results</span>
      </div>

      {/* Top info */}
      <div className="chartdesc">
        <span style={{ fontWeight: "700", fontSize: "24px" }}>
          {charts.length} Charts Generated Successfully
        </span>

        <div className="download_charts d-flex align-items-center justify-content-between">
          <span>
            Powered by DeepGuardX Intelligence • Data processed in 1.2s
          </span>

          <div className="chart-btns">
            <button
              className="download"
              onClick={handleDownloadZip}
              disabled={selectedCharts.length === 0}
            >
              Download selected <Download size={18} color="#425D86A8" />
            </button>

            <button className="select" onClick={handleSelectAll}>
              {selectedCharts.length === charts.length
                ? "Unselect All"
                : "Select All"}
            </button>
          </div>
        </div>
      </div>

      {/* Charts */}
      {charts.length === 0 ? (
        <p>No charts available</p>
      ) : (
        <div
          className="chartsarea"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(2, 1fr)",
            gap: "20px",
          }}
        >
          {charts.map((chart) => {
            const isSelected = selectedCharts.includes(chart.id);

            return (
              <div
                key={chart.id}
                className="linechart"
                onClick={() => toggleChart(chart.id)}
                style={{
                  border: `2px solid ${isSelected ? "#113567" : "#ddd"}`,
                  padding: "10px",
                  borderRadius: "12px",
                  width: "100%",
                  maxWidth: "590px",
                  margin: "0 auto",
                  height: "500px",
                  display: "flex",
                  flexDirection: "column",
                  cursor: "pointer",
                  transition: "0.3s",
                }}
              >
                {/* Top actions */}

                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    opacity: isSelected ? 1 : 0,
                    transition: "0.3s",
                  }}
                >
                  <div
                    className="custom-check-wrapper"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <input
                      id={`chart-${chart.id}`}
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleChart(chart.id)}
                    />
                    <Check className="check-icon" size={20} />
                  </div>

                  {/* <span
  onClick={(e) => {
    e.stopPropagation();
    setSelectedCharts(
      selectedCharts.filter((id) => id !== chart.id)
    );
  }}
  style={{
    color: "red",
    cursor: "pointer",
    fontWeight: "bold",
  }}
>
  Delete
</span> */}
                </div>

                {/* Chart Info */}
                <div className="chart-info">
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

                  <span
                    style={{
                      fontWeight: "400",
                      fontSize: "18px",
                    }}
                    className="mapping"
                  >
                    mapping:
                    <span className="badgee">{chart.mapping?.x?.column}</span>
                    <span>&</span>
                    <span className="badgee">{chart.mapping?.y?.column}</span>
                  </span>
                </div>

                {/* Chart */}
                <div className="lll" style={{ flex: 1 }}>
                  {chart.fig ? (
                    <Plot
                      data={chart.fig.data}
                      layout={{
                        ...chart.fig.layout,
                        autosize: true,
                      }}
                      useResizeHandler={true}
                      style={{ width: "100%", height: "100%" }}
                    />
                  ) : (
                    <p>No figure data</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
