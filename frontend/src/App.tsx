import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Upload from './pages/Upload';
import ExtractionReview from './pages/ExtractionReview';
import TemplateUpload from './pages/TemplateUpload';
import MappingReview from './pages/MappingReview';
import AuditTrail from './pages/AuditTrail';
import './index.css';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Upload />} />
          <Route path="extraction" element={<ExtractionReview />} />
          <Route path="template" element={<TemplateUpload />} />
          <Route path="mapping" element={<MappingReview />} />
          <Route path="audit" element={<AuditTrail />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
