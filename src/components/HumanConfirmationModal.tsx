import React from 'react';
import { ShieldAlert, AlertTriangle, Check, X, Shield, Lock } from 'lucide-react';
import { BrowserConfirmationRequest } from '../types';

interface HumanConfirmationModalProps {
  confirmation: BrowserConfirmationRequest | null;
  onConfirm: (confirmationId: string, approved: boolean) => void;
  onClose: () => void;
}

export const HumanConfirmationModal: React.FC<HumanConfirmationModalProps> = ({
  confirmation,
  onConfirm,
  onClose
}) => {
  if (!confirmation) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fade-in">
      <div className="bg-slate-900 border border-amber-500/40 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden text-slate-100">
        
        {/* Header */}
        <div className="p-5 border-b border-slate-800 bg-amber-950/30 flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
            <ShieldAlert size={26} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-white">Privileged Action Confirmation</h3>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-rose-500/20 text-rose-300 border border-rose-500/30">
                {confirmation.riskLevel} RISK
              </span>
            </div>
            <p className="text-xs text-amber-200/80 mt-0.5">
              The AI Agent is requesting permission to execute a privileged browser action.
            </p>
          </div>
        </div>

        {/* Action Details */}
        <div className="p-6 space-y-4 text-xs">
          <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
            <div className="flex justify-between">
              <span className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Action Type</span>
              <span className="font-mono text-cyan-300 font-bold">{confirmation.action}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400 font-semibold uppercase tracking-wider text-[10px]">Target Target</span>
              <span className="font-mono text-amber-200 truncate max-w-xs">{confirmation.target}</span>
            </div>
            <div className="pt-2 border-t border-slate-800/80">
              <span className="text-slate-400 block mb-1 font-semibold uppercase tracking-wider text-[10px]">Security Risk Reason</span>
              <p className="text-slate-200">{confirmation.reason}</p>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-start gap-2 text-amber-200">
            <AlertTriangle size={15} className="shrink-0 mt-0.5 text-amber-400" />
            <p className="text-[11px] leading-relaxed">
              Never approve actions you did not intend or expect the agent to perform. Approving will execute this directly in your live browser.
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/80 flex items-center justify-end gap-2.5">
          <button
            onClick={() => {
              onConfirm(confirmation.id, false);
              onClose();
            }}
            className="px-4 py-2 text-xs font-medium rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 flex items-center gap-1.5 transition-colors"
          >
            <X size={14} />
            Reject & Abort
          </button>

          <button
            onClick={() => {
              onConfirm(confirmation.id, true);
              onClose();
            }}
            className="px-5 py-2 text-xs font-bold rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white flex items-center gap-1.5 transition-all shadow-lg shadow-emerald-600/30"
          >
            <Check size={14} />
            Approve & Execute
          </button>
        </div>

      </div>
    </div>
  );
};
