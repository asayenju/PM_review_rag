'use client';

import { useEffect } from 'react';
import { pingHealth } from '../lib/api';

export default function BackendHealthPing() {
  useEffect(() => {
    pingHealth().catch(() => {
      // Best-effort warmup for hosted backends; user-facing API calls handle errors.
    });
  }, []);

  return null;
}
