import React from "react";

export default function AuthForm({ formik, fields, submitText, secondaryBtn, onSecondaryClick }) {
  return (
    <form onSubmit={formik.handleSubmit} className="auth-form">
      {fields.map((field) => (
        <div key={field.name} style={{ width: "100%", marginBottom: "8px" }}>
          <input
            name={field.name}
            type={field.type}
            placeholder={field.placeholder}
            value={formik.values[field.name]}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            className="auth-input"
          />
          {formik.touched[field.name] && formik.errors[field.name] && (
            <div style={{ color: "red", fontSize: "12px" }}>
              {formik.errors[field.name]}
            </div>
          )}
        </div>
      ))}

      <button type="submit" className="auth-button">
        {submitText}
      </button>

      {secondaryBtn && (
        <button
          type="button"
          className="auth-btn"
          onClick={onSecondaryClick}
        >
          {secondaryBtn}
        </button>
      )}
    </form>
  );
}