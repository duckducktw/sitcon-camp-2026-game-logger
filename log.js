
  // 1. Keep a reference to the original fetch function
const originalFetch = window.fetch;

// 2. Overwrite the global fetch function
window.fetch = async function(...args) {
  const url = args[0];
  console.log(`[Fetch Triggered] URL: ${url}`);
  
  try {
    const response = await originalFetch(...args);
    
    // 3. Clone the response so both the logger and the app can read it
    const clonedResponse = response.clone();
    
    // 4. Safely extract and log the JSON asynchronously
    clonedResponse.json()
      .then(jsonData => {
        console.log(`[Fetch Success] URL: ${url} | Status: ${response.status}`);
        console.log(`[Fetch Data]:`, jsonData);
        if (Object.keys(jsonData).includes("currentQuestionResult") && jsonData["status"] == "active") {
            console.log(
                jsonData["currentQuestionResult"]
            );


            fetch("http://localhost:8000/log", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(jsonData["currentQuestionResult"]),
            })
              .then((res) => res.json())
              .then((data) => console.log(data));
            
        }
      })
      .catch(() => {
        // Fallback in case the response is not valid JSON (e.g., HTML or plaintext)
        clonedResponse.text().then(textData => {
          console.log(`[Fetch Text Data]:`, textData);
        });
      });

    // 5. Return the pristine original response to your application
    return response;
    
  } catch (error) {
    console.error(`[Fetch Failed] URL: ${url} | Error:`, error);
    throw error; // Pass the error along to your application's error handlers
  }
};
