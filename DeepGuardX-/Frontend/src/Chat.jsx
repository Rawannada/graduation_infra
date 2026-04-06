import React from "react";
import { useState, useEffect, useRef } from "react";
import { PanelLeft, ArrowUp, Plus } from "lucide-react";
import { useLocation } from "react-router-dom";
import { ClipLoader } from "react-spinners";

export default function Chat() {
  const messagesEndRef = useRef(null);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingSummary, setLoadingSummary] = useState(true);

  const location = useLocation();

  const { summary, sessionId } = location.state || {};
  useEffect(() => {
    setLoadingSummary(true);
    const timer = setTimeout(() => setLoadingSummary(false), 4000); // fake 5s delay
    return () => clearTimeout(timer);
  }, []);


  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendQuestion() {
    if (!question.trim()) return;

    const userMessage = {
      role: "user",
      content: question,
    };
    // ضيف رسالة المستخدم فورًا
    setMessages((prev) => [...prev, userMessage]);
    setQuestion("");
    setLoading(true);

    try {
      const res = await fetch(`http://192.168.1.4:3000/upload/ask/${sessionId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      const data = await res.json();
      setMessages((prev) => {
        const newMessages = data.messages.filter(
          (msg) =>
            !prev.some(
              (old) => old.content === msg.content && old.role === msg.role
            )
        );
        return [...prev, ...newMessages];
      });
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chat">

      <div className="title d-flex align-items-center gap-2">
        <div className="icon">
          <PanelLeft />
        </div>
        <div className="span">chat</div>
      </div>

      <div className="chat-content">
        {loadingSummary ? (
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              height: "50vh", // نص ارتفاع الصفحة
              fontSize: "18px",
              fontWeight: "500",
            }}
          >
            <ClipLoader color="#4F204E" size={50} />
          </div>
        ) : (
          <div className="chat-container">
            <div className="messages-area">
              <div className="summary">
                <div className="sumtitle">Summary</div>
                <div className="sumcontent">
                  {summary ? summary : "No summary available yet."}
                </div>
              </div>
              <div className="messages">
                {messages.map((msg, index) => (
                  <div key={index} className={`message ${msg.role}`}>
                    {msg.content}
                    {msg.role === "assistant" && msg.sources && (
                      <ul className="sources">
                        {msg.sources.map((s, i) => (
                          <li key={i}>
                            {s.source} - page {s.page}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}

                {loading && <div className="message bot">Typing...</div>}
                <div ref={messagesEndRef} />
              </div>
              {/* هنا ممكن تضيفي chat messages بعد الـ summary */}
            </div>

            <div className="textbox">
              <div className="fileTitle d-flex align-items-center gap-1">
                <div className="icon">
                  <PanelLeft />
                </div>
                <div className="filename">File Name</div>
              </div>

              <div className="inputbox d-flex align-items-center justify-content-between">
                <input
                  type="text"
                  placeholder="ask this file a question ..."
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendQuestion()}
                />
                <div className="buttons d-flex align-items-center gap-3">
                  <div className="send">
                    <Plus size={20} />
                  </div>
                  <div className="upload" onClick={sendQuestion}>
                    <ArrowUp size={20} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
