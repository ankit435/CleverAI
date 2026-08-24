import React, { useState, useRef, useEffect } from 'react';
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
  Puzzle,
  Wand2,
  Code2,
  Globe,
  Image,
  FileText,
  HelpCircle,
  RotateCcw,
  Square
} from 'lucide-react';

interface SlashCommand {
  command: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  promptPrefix: string;
}

const SLASH_COMMANDS: SlashCommand[] = [
  {
    command: '/code',
    label: 'Code Generator',
    description: 'Write, debug, and explain clean code',
    icon: <Code2 size={15} style={{ color: '#3b82f6' }} />,
    promptPrefix: 'Write clean, modern, fully-commented code for: '
  },
  {
    command: '/search',
    label: 'Web Search',
    description: 'Find real-time live facts and information',
    icon: <Globe size={15} style={{ color: '#10b981' }} />,
    promptPrefix: 'Search the web and provide a comprehensive summary on: '
  },
  {
    command: '/image',
    label: 'Image Generator',
    description: 'Generate creative visual artwork',
    icon: <Image size={15} style={{ color: '#ec4899' }} />,
    promptPrefix: 'Create a detailed high-resolution image of: '
  },
  {
    command: '/summary',
    label: 'Summarize Text',
    description: 'Summarize text into key bullet points',
    icon: <FileText size={15} style={{ color: '#f59e0b' }} />,
    promptPrefix: 'Provide a concise, 3-bullet point executive summary of: '
  },
  {
    command: '/explain',
    label: 'Explain Simply',
    description: 'Explain a complex concept to a beginner',
    icon: <HelpCircle size={15} style={{ color: '#8b5cf6' }} />,
    promptPrefix: 'Explain this concept clearly and simply like I am 12 years old: '
  }
];

export const PromptInputCard: React.FC = () => {
  const [text, setText] = useState('');
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [showSlashMenu, setShowSlashMenu] = useState(false);
  const [selectedSlashIndex, setSelectedSlashIndex] = useState(0);
  const [isEnhancing, setIsEnhancing] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<any>(null);

  const {
    sendMessage,
    stopGenerating,
    isGenerating,
    activePluginIds,
    setIsPluginModalOpen,
    setIsPromptLibraryOpen,
    createNewChat
  } = useChatContext();

  // Auto-resize textarea height as content grows
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 220)}px`;
    }
  }, [text]);

  // Handle Slash Command detection
  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setText(val);

    if (val.startsWith('/')) {
      setShowSlashMenu(true);
      setSelectedSlashIndex(0);
    } else {
      setShowSlashMenu(false);
    }
  };

  const applySlashCommand = (cmd: SlashCommand) => {
    setText(cmd.promptPrefix);
    setShowSlashMenu(false);
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Navigate slash menu with keyboard
    if (showSlashMenu) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedSlashIndex(prev => (prev + 1) % SLASH_COMMANDS.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedSlashIndex(prev => (prev - 1 + SLASH_COMMANDS.length) % SLASH_COMMANDS.length);
        return;
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        applySlashCommand(SLASH_COMMANDS[selectedSlashIndex]);
        return;
      }
      if (e.key === 'Escape') {
        setShowSlashMenu(false);
        return;
      }
    }

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
    setShowSlashMenu(false);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setAttachedFile(e.target.files[0]);
    }
  };

  // Enhance prompt with AI sparkle
  const handleEnhancePrompt = () => {
    if (!text.trim()) return;
    setIsEnhancing(true);
    setTimeout(() => {
      const enhanced = `Please provide a comprehensive, step-by-step response with clear examples, best practices, and actionable insights for: "${text.trim()}".`;
      setText(enhanced);
      setIsEnhancing(false);
    }, 400);
  };

  const toggleRecording = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in your browser.');
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

      recognition.onstart = () => setIsRecording(true);

      recognition.onresult = (event: any) => {
        let transcript = '';
        for (let i = 0; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        if (transcript) {
          setText(prev => (prev ? `${prev} ${transcript}` : transcript));
        }
      };

      recognition.onerror = () => setIsRecording(false);
      recognition.onend = () => setIsRecording(false);

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      console.warn('Speech recognition error:', err);
      setIsRecording(false);
    }
  };

  const activeCount = activePluginIds.length;

  return (
    <div className="prompt-card" style={{ position: 'relative' }}>
      {/* Slash Command Autocomplete Popover */}
      {showSlashMenu && (
        <div className="slash-menu-popover">
          <div className="slash-menu-header">
            <span>COMMANDS</span>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Use ↑↓ and Enter</span>
          </div>
          {SLASH_COMMANDS.map((cmd, idx) => (
            <div
              key={cmd.command}
              className={`slash-menu-item ${selectedSlashIndex === idx ? 'selected' : ''}`}
              onClick={() => applySlashCommand(cmd)}
            >
              <div className="slash-icon-box">{cmd.icon}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: '13px' }}>{cmd.label} <span style={{ color: 'var(--primary)', fontSize: '12px' }}>{cmd.command}</span></div>
                <div style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>{cmd.description}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Top Bar Header inside input card */}
      <div className="prompt-card-header">
        <div className="prompt-card-label">
          <MessageSquarePlus size={16} style={{ color: 'var(--primary)' }} />
          <span>Prompt Assistant</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {text.trim().length > 0 && (
            <button
              type="button"
              className="prompt-action-pill"
              onClick={handleEnhancePrompt}
              title="Enhance prompt with AI"
              style={{ color: 'var(--primary)', padding: '3px 8px', fontSize: '11.5px' }}
            >
              <Wand2 size={12} className={isEnhancing ? 'animate-spin' : ''} />
              <span>{isEnhancing ? 'Enhancing...' : 'Enhance'}</span>
            </button>
          )}

          <button 
            className="btn-icon-subtle"
            onClick={() => setIsPluginModalOpen(true)}
            title="Configure Plugin Tools"
          >
            <SlidersHorizontal size={16} />
          </button>
        </div>
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
          marginBottom: '8px',
          alignSelf: 'flex-start'
        }}>
          <Paperclip size={12} />
          <span>{attachedFile.name}</span>
          <span style={{ fontSize: '10.5px', opacity: 0.8 }}>({(attachedFile.size / 1024).toFixed(1)} KB)</span>
          <button 
            onClick={() => setAttachedFile(null)}
            style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', display: 'flex' }}
          >
            <X size={12} />
          </button>
        </div>
      )}

      {/* Main Textarea */}
      <textarea
        ref={textareaRef}
        className="prompt-textarea"
        placeholder={isRecording ? "Listening to your voice..." : "Ask anything, or type '/' for commands..."}
        value={text}
        onChange={handleTextChange}
        onKeyDown={handleKeyDown}
        disabled={isGenerating}
        rows={1}
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
            <Mic size={14} />
            <span>{isRecording ? 'Listening...' : 'Voice'}</span>
          </button>

          <button 
            className="prompt-action-pill"
            onClick={() => setIsPromptLibraryOpen(true)}
          >
            <BookOpen size={14} />
            <span>Library</span>
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

          {/* Submit / Stop Button */}
          {isGenerating ? (
            <button
              className="btn-submit-prompt"
              onClick={stopGenerating}
              title="Stop Generating"
              style={{ background: '#ef4444' }}
            >
              <Square size={16} fill="currentColor" />
            </button>
          ) : (
            <button
              className="btn-submit-prompt"
              onClick={handleSend}
              disabled={!text.trim() && !attachedFile}
              title="Send Message (Enter)"
            >
              <ArrowUp size={18} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
