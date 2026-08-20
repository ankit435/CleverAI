import React, { useState, useRef } from 'react';
import { useChatContext } from '../context/ChatContext';
import { 
  Paperclip, 
  Sparkles, 
  BookOpen, 
  SlidersHorizontal, 
  ArrowUp, 
  Mic, 
  X,
  MessageSquarePlus,
  Puzzle
} from 'lucide-react';

export const PromptInputCard: React.FC = () => {
  const [text, setText] = useState('');
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    sendMessage,
    isGenerating,
    plugins,
    activePluginIds,
    toggleActivePluginId,
    setIsPluginModalOpen,
    setIsPromptLibraryOpen
  } = useChatContext();

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    if (!text.trim() && !attachedFile) return;
    sendMessage(text, attachedFile);
    setText('');
    setAttachedFile(null);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setAttachedFile(e.target.files[0]);
    }
  };

  const recognitionRef = useRef<any>(null);

  const toggleRecording = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in your browser. Please type your prompt.');
      return;
    }

    if (isRecording) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsRecording(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = 'en-US';
      recognition.interimResults = true;
      recognition.continuous = false;

      recognition.onstart = () => {
        setIsRecording(true);
      };

      recognition.onresult = (event: any) => {
        let transcript = '';
        for (let i = 0; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        if (transcript) {
          setText(prev => (prev ? `${prev} ${transcript}` : transcript));
        }
      };

      recognition.onerror = (event: any) => {
        console.warn('Speech recognition error:', event.error);
        setIsRecording(false);
      };

      recognition.onend = () => {
        setIsRecording(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      console.warn('Speech recognition start failed:', err);
      setIsRecording(false);
    }
  };

  const activeCount = activePluginIds.length;

  return (
    <div className="prompt-card">
      {/* Top Bar Header inside input card */}
      <div className="prompt-card-header">
        <div className="prompt-card-label">
          <MessageSquarePlus size={16} style={{ color: 'var(--primary)' }} />
          <span>Start new chat</span>
        </div>

        <button 
          className="btn-icon-subtle"
          onClick={() => setIsPluginModalOpen(true)}
          title="Configure Plugin Tools"
        >
          <SlidersHorizontal size={16} />
        </button>
      </div>

      {/* Attached file preview tag if file attached */}
      {attachedFile && (
        <div style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          padding: '4px 10px',
          backgroundColor: 'var(--primary-light)',
          color: 'var(--primary)',
          borderRadius: '12px',
          fontSize: '12px',
          fontWeight: 600,
          marginBottom: '8px'
        }}>
          <Paperclip size={12} />
          <span>{attachedFile.name}</span>
          <button 
            onClick={() => setAttachedFile(null)}
            style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}
          >
            <X size={12} />
          </button>
        </div>
      )}

      {/* Main Textarea */}
      <textarea
        className="prompt-textarea"
        placeholder={isRecording ? "Listening to your voice..." : "How can AI help you today?"}
        value={text}
        onChange={e => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={isGenerating}
      />

      {/* Hidden File Input */}
      <input 
        type="file" 
        ref={fileInputRef} 
        style={{ display: 'none' }} 
        onChange={handleFileChange} 
      />

      {/* Bottom Bar Actions */}
      <div className="prompt-card-footer">
        <div className="prompt-actions-left">
          <button 
            className="prompt-action-pill"
            onClick={() => fileInputRef.current?.click()}
          >
            <Paperclip size={14} />
            <span>Attach</span>
          </button>

          <button 
            className={`prompt-action-pill ${isRecording ? 'recording' : ''}`}
            onClick={toggleRecording}
            style={isRecording ? { color: '#ef4444', borderColor: '#ef4444' } : {}}
          >
            {isRecording ? <Sparkles size={14} className="animate-spin" /> : <Sparkles size={14} />}
            <span>{isRecording ? 'Listening...' : 'Voice message'}</span>
          </button>

          <button 
            className="prompt-action-pill"
            onClick={() => setIsPromptLibraryOpen(true)}
          >
            <BookOpen size={14} />
            <span>Prompt library</span>
          </button>
        </div>

        <div className="prompt-actions-right">
          {/* Active Tools Selector Pill */}
          <button 
            className="btn-tool-pill"
            onClick={() => setIsPluginModalOpen(true)}
            title="Manage Active Tools"
          >
            <Puzzle size={14} />
            <span>Tools ({activeCount})</span>
          </button>

          {/* Submit Button */}
          <button 
            className="btn-submit-prompt"
            onClick={handleSend}
            disabled={(!text.trim() && !attachedFile) || isGenerating}
            title="Send Message (Enter)"
          >
            <ArrowUp size={18} />
          </button>
        </div>
      </div>
    </div>
  );
};
