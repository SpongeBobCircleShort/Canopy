// src/api.js – Supabase based data layer
import { supabase } from './supabaseClient.js';

/** Auth **/
export async function signup({ email, password }) {
  const { data, error } = await supabase.auth.signUp({ email, password });
  if (error) throw error;
  const { session } = data;
  if (session?.access_token) await supabase.auth.setSession(session.access_token);
  return { access_token: session?.access_token };
}

export async function login({ email, password }) {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw error;
  const { session } = data;
  if (session?.access_token) await supabase.auth.setSession(session.access_token);
  return { access_token: session?.access_token };
}

export async function logout() {
  const { error } = await supabase.auth.signOut();
  if (error) throw error;
}

/** Helpers **/
function handleError(error) {
  if (error) throw new Error(error.message || 'Supabase error');
}

/** Health check **/
export async function fetchHealth() {
  // Simple static health check
  return { status: 'ok' };
}

/** User profile **/
export async function fetchMe(token) {
  const { data: { user }, error } = await supabase.auth.getUser();
  handleError(error);
  return {
    id: user?.id,
    email: user?.email,
    role: user?.app_metadata?.role || 'user',
    org_id: user?.app_metadata?.org_id || null,
  };
}

/** Alerts **/
export async function fetchAlerts(token, params = {}) {
  const { data, error } = await supabase.from('alerts').select('*').match(params);
  handleError(error);
  return data;
}

/** Sensors **/
export async function fetchSensors(token) {
  const { data, error } = await supabase.from('sensors').select('*');
  handleError(error);
  return data;
}

/** Regions **/
export async function fetchRegions(token) {
  const { data, error } = await supabase.from('regions').select('*');
  handleError(error);
  return data;
}

/** Satellite Changes **/
export async function fetchSatelliteChanges(token) {
  const { data, error } = await supabase.from('satellite_changes').select('*');
  handleError(error);
  return data;
}

/** Create Satellite Change **/
export async function createSatelliteChange(token, payload) {
  const { data, error } = await supabase.from('satellite_changes').insert(payload).single();
  handleError(error);
  return data;
}

/** NDVI Batches (placeholder) **/
export async function fetchNdviBatches(token) {
  const { data, error } = await supabase.from('ndvi_batches').select('*');
  if (error) return [];
  return data;
}

/** Upload NDVI CSV (placeholder) **/
export async function uploadNdviCsv(token, { regionId, lossThreshold, defaultConfidence, file }) {
  throw new Error('uploadNdviCsv not implemented');
}

/** Fusion (placeholder) **/
export async function runFusion(token, payload = {}) {
  const { data, error } = await supabase.functions.invoke('fusion-run', { body: payload });
  if (error) throw error;
  return data;
}

/** Export Alerts URL **/
export function exportAlertsUrl() {
  return '';
}

/** Download Alerts CSV (placeholder) **/
export async function downloadAlertsCsv(token) {
  throw new Error('downloadAlertsCsv not implemented');
}
