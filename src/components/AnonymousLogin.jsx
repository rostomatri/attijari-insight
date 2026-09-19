import { useState } from "react";

export default function AnonymousLogin() {
  const [formData, setFormData] = useState({
    email: "",
    department: "",
    role: "",
    seniority: "",
    work_mode: "",
  });

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const response = await fetch("http://localhost:8000/api/anonymous-login/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formData),
    });

    const data = await response.json();
    alert(data.message);
  };

  return (
    <div style={{ maxWidth: "500px", margin: "auto" }}>
      <h2>Connexion anonyme</h2>

      <form onSubmit={handleSubmit}>
        <input
          type="email"
          name="email"
          placeholder="Email professionnel"
          required
          onChange={handleChange}
        />

        <select name="department" onChange={handleChange} required>
          <option value="">Département</option>
          <option value="Front">Front Office</option>
          <option value="Back">Back Office</option>
          <option value="IT">IT</option>
        </select>

        <select name="role" onChange={handleChange} required>
          <option value="">Rôle</option>
          <option value="Agent">Agent</option>
          <option value="Manager">Manager</option>
        </select>

        <select name="seniority" onChange={handleChange} required>
          <option value="">Ancienneté</option>
          <option value="0-2">0–2 ans</option>
          <option value="3-5">3–5 ans</option>
          <option value="6+">6+ ans</option>
        </select>

        <select name="work_mode" onChange={handleChange} required>
          <option value="">Mode de travail</option>
          <option value="3P-2H">3j présentiel / 2j hybride</option>
          <option value="5P">100% présentiel</option>
        </select>

        <button type="submit">Continuer</button>
      </form>
    </div>
  );
}