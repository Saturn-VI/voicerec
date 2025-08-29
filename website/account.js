function logout() {
  fetch("/account/logout", {
    method: "POST",
    credentials: "include",
  }).then((response) => {
    if (response.ok) {
      window.location.href = "/";
    } else {
      alert("Logout failed.");
    }
  });
}
