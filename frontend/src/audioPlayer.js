let currentSpeakAbort = null;

export async function speakText(fullText) {
  const endpoint = `${import.meta.env.VITE_API_URL}/speak`;

  // Allow external stop
  if (currentSpeakAbort) currentSpeakAbort.abort();
  const abort = { aborted: false, abort: () => (abort.aborted = true) };
  currentSpeakAbort = abort;

  const splitRes = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: fullText, split: true }),
  });

  if (!splitRes.ok) {
    console.error("Failed to split text:", await splitRes.text());
    return;
  }

  const { sentences } = await splitRes.json();

  let i = 0;
  let nextAudioBlob = await fetchAudioBlob(sentences[i++], endpoint);
  while (i <= sentences.length && !abort.aborted) {
    const currentBlob = nextAudioBlob;
    const nextSentence = sentences[i];
    const nextAudioPromise = nextSentence
      ? fetchAudioBlob(nextSentence, endpoint)
      : Promise.resolve(null);

    await playAudioBlob(currentBlob, abort);
    nextAudioBlob = await nextAudioPromise;
    i++;
  }
}

export function stopSpeaking() {
  if (currentSpeakAbort) currentSpeakAbort.abort();
}

async function fetchAudioBlob(sentence, endpoint) {
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: sentence }),
    });
    if (!response.ok) {
      console.error("TTS error:", await response.text());
      return null;
    }
    return await response.blob();
  } catch (err) {
    console.error("TTS fetch error:", err);
    return null;
  }
}

function playAudioBlob(blob, abort) {
  return new Promise((resolve) => {
    if (abort.aborted) return resolve();
    const audio = new Audio(URL.createObjectURL(blob));

    const cleanUp = () => {
      audio.pause();
      audio.src = "";
      resolve();
    };

    audio.onended = cleanUp;
    audio.onerror = cleanUp;
    audio.play();

    const interval = setInterval(() => {
      if (abort.aborted) {
        clearInterval(interval);
        cleanUp();
      }
    }, 100);
  });
}
