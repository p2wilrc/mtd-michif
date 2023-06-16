<?php

/* Allow a few origins including a not entirely secure one for testing. */
if ($_SERVER["HTTP_ORIGIN"] == "https://michif.ecolingui.ca")
    header("Access-Control-Allow-Origin: https://michif.ecolingui.ca");
else if (str_starts_with($_SERVER["HTTP_ORIGIN"], "http://192.168"))
    header("Access-Control-Allow-Origin: " . $_SERVER["HTTP_ORIGIN"]);
else
    header("Access-Control-Allow-Origin: https://dictionary.michif.org");

if (!isset($_GET["id"])) {
    http_reponse_code(400);
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