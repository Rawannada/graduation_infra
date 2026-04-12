import React from "react";
import { useState, useEffect, useRef } from "react";
import {
  PanelRight,
  ChevronLeft,
  ChevronRight,
  FileText,
  PanelLeft,
  ArrowUp,
  Plus,
    Brain, CheckCircle , Sparkle
} from "lucide-react";
import { useLocation } from "react-router-dom";
import { ClipLoader } from "react-spinners";

export default function Chat() {
  const [fileOpen, setFileOpen] = useState(true); // true يعني الملف ظاهر

  const [pages, setPages] = useState([]);
  const [currentPage, setCurrentPage] = useState(0);
  const [fileContent, setFileContent] = useState("");
  const messagesEndRef = useRef(null);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [message, setMessage] = useState("");
  const [summary, setSummary] = useState(null);
  const [loadingStep, setLoadingStep] = useState("");
const [thinkingStep, setThinkingStep] = useState("");
  const location = useLocation();
  const [summaryError, setSummaryError] = useState(false);
  const { fileUrl, fileId } = location.state || {};
  const accessToken = location.state?.accessToken || "";

  //summarize
  const handleSummarize = async () => {
    if (!fileId) return;

    setLoadingSummary(true);
    setMessage("");

    try {
      const res = await fetch(`http://localhost:3000/ai/summarize/${fileId}`, {
        method: "POST",
        headers: {
          Authorization: `bearer ${accessToken}`,
        },
      });
      if (!res.ok) {
        throw new Error("Server error");
      }
      const data = await res.json();

      // السيرفر ممكن يرد بأي اسم مفتاح
      const sum = data.summary;

      setSummary(sum || "No summary available.");
      setMessage(data.message || "");
    } catch (err) {
      console.error(err);
      setMessage("Error summarizing file");
    } finally {
      setLoadingSummary(false);
    }
  };

  // ask question
async function sendQuestion() {
  if (!question.trim()) return;

  setMessages((prev) => [...prev, { role: "user", content: question }]);

  const currentQuestion = question;
  setQuestion("");

  setLoading(true);

  try {
    // ثابتة
    setLoadingStep("Reading the file");

    await new Promise((r) => setTimeout(r, 700));

    // المتغيرة
    setThinkingStep("Thinking...");

    const res = await fetch(`http://localhost:3000/ai/ask/${fileId}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `bearer ${accessToken}`,
      },
      body: JSON.stringify({ question: currentQuestion }),
    });

    const data = await res.json();

    // التحويل هنا
    setThinkingStep("Finished thinking...");

    await new Promise((r) => setTimeout(r, 500));

    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: data.answer || "No answer found" },
    ]);

  } catch (err) {
    setMessages((prev) => [
      ...prev,
      { role: "assistant", content: "Error retrieving answer" },
    ]);
  } finally {
    setLoading(false);
    setLoadingStep("");
    setThinkingStep("");
  }
}
  // async function sendQuestion() {
  //   if (!question.trim()) return;

  //   const userMessage = { role: "user", content: question };
  //   setMessages((prev) => [...prev, userMessage]);
  //   const currentQuestion = question;
  //   setQuestion("");
  //   setLoading(true);

  //   try {
  //     const res = await fetch(`http://localhost:3000/ai/ask/${fileId}`, {
  //       method: "POST",
  //       headers: {
  //         "Content-Type": "application/json",
  //         Authorization: `bearer ${accessToken}`,
  //       },
  //       body: JSON.stringify({ question: currentQuestion }),
  //     });
  //     if (!res.ok) {
  //       throw new Error("Server error");
  //     }
  //     const data = await res.json();

  //     const assistantMessage = {
  //       role: "assistant",
  //       content: data.answer || "No answer found",
  //     };
  //     setMessages((prev) => [...prev, assistantMessage]);
  //   } catch (err) {
  //     console.error(err);

  //     setMessages((prev) => [
  //       ...prev,
  //       { role: "assistant", content: "Error retrieving answer" },
  //     ]);
  //   } finally {
  //     setLoading(false);
  //   }
  // }

  //get chat history
  const fetchChatHistory = async () => {
    if (!fileId) return;
    try {
      const res = await fetch(`http://localhost:3000/ai/chat/${fileId}`, {
        headers: { Authorization: `bearer ${accessToken}` },
      });
      if (!res.ok) {
        throw new Error("Server error");
      }
      const data = await res.json();
      if (data.chats) {
        const history = data.chats.flatMap((c) => [
          { role: "user", content: c.question },
          { role: "assistant", content: c.answer },
        ]);
        setMessages(history);
      }
    } catch (err) {
      console.error("History error:", err);
    }
  };
  const hasFetched = useRef({});

  useEffect(() => {
    if (!fileId || !accessToken) return;
    if (hasFetched.current[fileId]) return;

    hasFetched.current[fileId] = true;

    handleSummarize();
    fetchChatHistory();
  }, [fileId, accessToken]);
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  if (loadingSummary) {
    return (
      <div className="full-loader">
        <ClipLoader size={50} />
      </div>
    );
  }

  if (summaryError) {
    return (
      <div className="full-loader">
        <p>Failed to load summary </p>
      </div>
    );
  }
  return (
    <div className="chat">
      <input
        type="file"
        hidden
        id="fileUpload"
        onChange={(e) => {
          const selectedFile = e.target.files[0];
          if (!selectedFile) return;

          const reader = new FileReader();

          reader.onload = (e) => {
            const text = e.target.result;

            // 👇 تقسيم لصفحات
            const lines = text.split("\n");
            const pageSize = 20;

            const pagesArray = [];

            for (let i = 0; i < lines.length; i += pageSize) {
              pagesArray.push(lines.slice(i, i + pageSize).join("\n"));
            }

            setPages(pagesArray);
            setCurrentPage(0);
          };

          reader.readAsText(selectedFile);
        }}
      />
      <div className="title">
        <PanelLeft size={20} />
        <span>file name</span>
        <div className="closefile" onClick={() => setFileOpen((prev) => !prev)}>
          {" "}
          {fileOpen ? <PanelLeft size={20} /> : <PanelRight size={20} />}
        </div>
      </div>

      <div className="chatlayout">
        {" "}
        <div className="chat-container  ">
          <div className="messages">
            {/* summary جوه الـ scroll */}
            <div className="summary">
              <div className="sumtitle">Summary</div>
              <div className="sumcontent">{summary}</div>
            </div>
            {/* الرسائل */}
            {messages.map((msg, index) => (
              <div key={index} className={`message ${msg.role}`}>
                {msg.content}
                {msg.role === "assistant" &&
                  msg.sources &&
                  msg.sources.length > 0 && (
                    <ul className="sources">
                      {[
                        ...new Map(
                          msg.sources
                            .filter((s) => s.source && s.page)
                            .map((s) => [s.source + "-" + s.page, s]),
                        ).values(),
                      ].map((s, i) => (
                        <li key={i}>
                          {s.source} - page {s.page}
                        </li>
                      ))}
                    </ul>
                  )}
              </div>
            ))}
         {loading && (
  <div className="message assistant loading-box">
    
    <div className="step">
      <FileText size={16} />
      <span>{loadingStep}</span>
    </div>

    <div className="step">
      {thinkingStep === "Finished thinking..." ? (
        < Sparkle size={20} />
      ) : (
        <Brain size={16} />
      )}
      <span>{thinkingStep}</span>
    </div>

  </div>
)}
            <div ref={messagesEndRef} />
          </div>
          <div className="textbox">
            <div className="title">
              <FileText size={20} />
              <span>file name</span>
            </div>

            <div className="inputbox d-flex align-items-center justify-content-between">
              <textarea
                // type="text"
                placeholder="ask this file a question ..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendQuestion();
                  }
                }}
              />
              <div className="buttons d-flex align-items-center gap-3">
                <div
                  style={{ cursor: "pointer" }}
                  className="send"
                  onClick={() => document.getElementById("fileUpload").click()}
                >
                  <Plus size={20} />
                </div>
                <div
                  className="upload"
                  onClick={question.trim() ? sendQuestion : null}
                  style={{
                    opacity: question.trim() ? 1 : 0.5,
                    cursor: question.trim() ? "pointer" : "not-allowed",
                  }}
                >
                  <ArrowUp size={20} />
                </div>
              </div>
            </div>
          </div>
        </div>
        {fileOpen && (
          <div className="thefile">
            {/* <div className="pagination">
              <button
                onClick={() => setCurrentPage((p) => p - 1)}
                disabled={currentPage === 0}
              >
                <ChevronLeft size={17} />
              </button>

              <div className="pgc d-flex">
                <span className="n1">{currentPage + 1}</span>
                <span>of {pages.length}</span>
              </div>
              <button
                onClick={() => setCurrentPage((p) => p + 1)}
                disabled={currentPage === pages.length - 1}
              >
                <ChevronRight size={17} />
              </button>
            </div> */}
            <div  className="showfile">
              {fileUrl ? (
                <iframe
                  src={fileUrl}
                  width="100%"
                  height="100%"
                  style={{ border: "none", background: "green" }}
                />
              ) : (
                <span>No file loaded</span>
              )}
              <div className="filename"></div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
