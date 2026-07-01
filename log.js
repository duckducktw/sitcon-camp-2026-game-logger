
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
            
        } else if (Object.keys(jsonData).includes("currentQuestion") && jsonData["status"] == "active"){

          const responseSys = {
            "A": ".px-6 > div:nth-child(3) > div:nth-child(1) > button:nth-child(1)",
            "B": ".px-6 > div:nth-child(3) > div:nth-child(2) > button:nth-child(1)",
            "C": ".px-6 > div:nth-child(3) > div:nth-child(3) > button:nth-child(1)",
            "D": ".px-6 > div:nth-child(3) > div:nth-child(4) > button:nth-child(1)"
          }

          const fallbackResponseSys = {
            "A": ".px-6 > div:nth-child(4) > div:nth-child(1) > button:nth-child(1)",
            "B": ".px-6 > div:nth-child(4) > div:nth-child(2) > button:nth-child(1)",
            "C": ".px-6 > div:nth-child(4) > div:nth-child(3) > button:nth-child(1)",
            "D": ".px-6 > div:nth-child(4) > div:nth-child(4) > button:nth-child(1)"
          }

          fetch(`http://localhost:8000/answer/${jsonData["currentQuestion"]["questionId"]}`)
              .then((res) => res.json())
              .then((answerData) => {
                console.log(answerData);
                setTimeout(() => {
                  const selector = responseSys[answerData["answer"]];
                  let button = document.querySelector(selector);
                  if (button) {
                    button.click();
                    return;
                  }

                  const fallbackSelector = fallbackResponseSys[answerData["answer"]];
                  const fallbackButton = fallbackSelector ? document.querySelector(fallbackSelector) : null;
                  if (fallbackButton) {
                    fallbackButton.click();
                  } else {
                    console.log(`[No button found] questionId: ${jsonData["currentQuestion"]["questionId"]}`);
                  }
                }, 50);
              });
        } else if (jsonData["status"] == "completed") {
          setTimeout(() => {
            history.pushState({}, "", "/battle/");
            window.dispatchEvent(new PopStateEvent("popstate"));

            setTimeout(() => {
              const secondaryButton = document.querySelector("button.bg-secondary:nth-child(1)");
              if (secondaryButton) {
                secondaryButton.click();
              } else {
                console.log(`[No button found] selector: button.bg-secondary:nth-child(1)`);
              }

              setTimeout(() => {
                const button = document.querySelector("button.h-10");
                if (button) {
                  button.click();
                } else {
                  console.log(`[No button found] selector: button.h-10`);
                }
              }, 3000);
            }, 3000);
          }, 3000);
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

