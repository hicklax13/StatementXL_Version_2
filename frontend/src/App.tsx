import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Upload from './pages/Upload';
import ExtractionReview from './pages/ExtractionReview';
import TemplateUpload from './pages/TemplateUpload';
import MappingReview from './pages/MappingReview';
import AuditTrail from './pages/AuditTrail';
import TemplateLibrary from './pages/TemplateLibrary';
import BatchUpload from './pages/BatchUpload';
import Login from './pages/Login';
import Register from './pages/Register';
import './index.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Auth routes (outside layout) */}
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* App routes (with layout) */}
        <Route path="/" element={<Layout />}>
          <Route index element={<Upload />} />
          <Route path="extraction" element={<ExtractionReview />} />
          <Route path="template" element={<TemplateUpload />} />
          <Route path="mapping" element={<MappingReview />} />
          <Route path="audit" element={<AuditTrail />} />
          <Route path="library" element={<TemplateLibrary />} />
          <Route path="batch" element={<BatchUpload />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;

