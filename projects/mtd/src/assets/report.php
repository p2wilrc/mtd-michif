<?php

/* Only run if there is an origin (this is a REST API and nothing else) */
if (!isset($_SERVER["HTTP_ORIGIN"])) {
    http_response_code(401);
    return;
}

/* Restrict origins and send CORS header */
if ($_SERVER["HTTP_ORIGIN"] == "https://michif.ecolingui.ca")
    header("Access-Control-Allow-Origin: https://michif.ecolingui.ca");
else if ($_SERVER["HTTP_ORIGIN"] == "https://dictionary.michif.org")
    header("Access-Control-Allow-Origin: https://dictionary.michif.org");
else {
    http_response_code(401);
    return;
}

if (!isset($_GET["id"])) {
    http_response_code(400);
}
else {
    $entry_id = urlencode($_GET["id"]);
    $subject = "Review entry $entry_id";
    if (isset($_GET["word"]))
        $subject .= " (" . $_GET["word"] . ")";
    if (isset($_GET["desc"]))
        $message = $_GET["desc"] . "\n\n";
    $message .= "See: ";
    if (isset($_GET["url"]))
        $message .= $_GET["url"];
    else
        $message .= "https://dictionary.michif.org/search?show=$entry_id";
    $message .= "\n";
    mail("dictionary@p2wilr.org", $subject, $message);
}

?>